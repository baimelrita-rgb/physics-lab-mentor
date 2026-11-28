"""Teacher accounts and login.

- Passwords are stored only as PBKDF2-SHA256 hashes with a per-user salt (var/state/teachers.json).
- Login sets a signed, HttpOnly cookie valid for 12 hours (HMAC-SHA256 with a server secret).
- 5 failed logins for a username lock it for 5 minutes.
- No accounts defined = demo mode: teacher screens stay open, and the UI says so.
Accounts are added with:  python3 tools/add_teacher.py <username> "<display name>"
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

ITERATIONS = 200_000
COOKIE = "lm_teacher"
TTL = 12 * 3600
MAX_FAILS, LOCK_SECONDS = 5, 300
DEMO_USER = "demo"


class AuthError(Exception):
    pass


class Auth:
    def __init__(self, state_dir: Path, clock=time.time):
        self.dir = Path(state_dir)
        self.clock = clock
        self.fails: dict[str, list[float]] = {}

    # ---------- accounts ----------
    @property
    def _file(self) -> Path:
        return self.dir / "teachers.json"

    def teachers(self) -> dict:
        return json.loads(self._file.read_text(encoding="utf-8")) if self._file.exists() else {}

    @property
    def demo(self) -> bool:
        """Open teacher screens only when explicitly asked for (DEMO=1) and no account exists."""
        from .security import demo_mode
        return not self.teachers() and demo_mode()

    @property
    def has_accounts(self) -> bool:
        return bool(self.teachers())

    def add_teacher(self, username: str, name: str, password: str):
        username = username.strip().lower()
        if not username.replace("_", "").replace(".", "").isalnum() or len(username) > 40:
            raise AuthError("username: letters, digits, '.' or '_' only")
        if len(password) < 8:
            raise AuthError("password must be at least 8 characters")
        salt = secrets.token_hex(16)
        users = self.teachers()
        users[username] = {"name": name.strip() or username, "salt": salt, "iterations": ITERATIONS,
                           "hash": self._hash(password, salt, ITERATIONS)}
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps(users, ensure_ascii=False, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._file)

    @staticmethod
    def _hash(password: str, salt: str, iterations: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations).hex()

    # ---------- login ----------
    def login(self, username: str, password: str) -> str:
        """Returns a cookie value, or raises AuthError."""
        username = username.strip().lower()
        now = self.clock()
        recent = [t for t in self.fails.get(username, []) if now - t < LOCK_SECONDS]
        self.fails[username] = recent
        if len(recent) >= MAX_FAILS:
            raise AuthError("locked")
        user = self.teachers().get(username)
        # Hash even for unknown users, so response time does not reveal which usernames exist.
        salt, it = (user["salt"], user["iterations"]) if user else ("00" * 16, ITERATIONS)
        ok = user is not None and hmac.compare_digest(self._hash(password, salt, it), user["hash"])
        if not ok:
            self.fails[username].append(now)
            raise AuthError("wrong username or password")
        self.fails.pop(username, None)
        return self._sign({"u": username, "exp": int(now + TTL)})

    def user_from_cookie(self, value: str | None) -> str | None:
        if not value or "." not in value:
            return None
        body, sig = value.rsplit(".", 1)
        if not hmac.compare_digest(sig, self._mac(body)):
            return None
        try:
            data = json.loads(base64.urlsafe_b64decode(body.encode()))
        except ValueError:
            return None
        if data.get("exp", 0) < self.clock() or data.get("u") not in self.teachers():
            return None
        return data["u"]

    def name(self, username: str) -> str:
        return self.teachers().get(username, {}).get("name", username)

    # ---------- signing ----------
    def _secret(self) -> bytes:
        env = os.environ.get("SECRET_KEY")
        if env:
            return env.encode()
        f = self.dir / "secret.key"
        if not f.exists():
            self.dir.mkdir(parents=True, exist_ok=True)
            f.write_text(secrets.token_hex(32))
            os.chmod(f, 0o600)
        return f.read_text().strip().encode()

    def _mac(self, body: str) -> str:
        return hmac.new(self._secret(), body.encode(), hashlib.sha256).hexdigest()

    def _sign(self, data: dict) -> str:
        body = base64.urlsafe_b64encode(json.dumps(data).encode()).decode()
        return f"{body}.{self._mac(body)}"
