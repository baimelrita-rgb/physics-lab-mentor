"""Access protection (MVP package 3).

- Group token: a random secret per session, kept in an HttpOnly cookie that is sent only to
  /api/sessions/<id>. Knowing a session id (it shows in the URL) is not enough to act for a group.
- Rate limits on FAILED attempts per client IP (a school shares one IP behind NAT, so
  successful joins are never counted).
- Station tokens: one token per station, stored only as a SHA-256 hash; a token is valid
  only for its own station.
- CSV cells that a spreadsheet would run as a formula are neutralized.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

SESSION_COOKIE = "lm_s"


def new_token() -> str:
    return secrets.token_urlsafe(24)


def demo_mode() -> bool:
    return os.environ.get("DEMO") == "1"


def cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "1") == "1"


def client_ip(request) -> str:
    if os.environ.get("TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "?"


class RateLimiter:
    """At most `limit` events per `window` seconds per key (sliding window)."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.events: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def _trim(self, q: deque, now: float):
        while q and now - q[0] > self.window:
            q.popleft()

    def blocked(self, key: str) -> bool:
        with self.lock:
            q = self.events[key]
            self._trim(q, self.clock())
            return len(q) >= self.limit

    def hit(self, key: str):
        with self.lock:
            q = self.events[key]
            now = self.clock()
            self._trim(q, now)
            q.append(now)


def csv_safe(value):
    """A cell starting with = + - @ (or tab / CR) is prefixed with ' so Excel shows it as text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


class StationTokens:
    """stations.json in the state folder: {station_id: {"hash": sha256(token), "created": ts}}."""

    def __init__(self, state_dir: Path):
        self.file = Path(state_dir) / "stations.json"

    def _load(self) -> dict:
        return json.loads(self.file.read_text(encoding="utf-8")) if self.file.exists() else {}

    def issue(self, station_id: str) -> str:
        if not station_id.replace("-", "").replace("_", "").isalnum() or len(station_id) > 40:
            raise ValueError("station id: letters, digits, '-' or '_'")
        token = new_token()
        data = self._load()
        data[station_id] = {"hash": hashlib.sha256(token.encode()).hexdigest(), "created": time.time()}
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.file)
        return token

    def valid(self, station_id: str, token: str | None) -> bool:
        if not token:
            return False
        if demo_mode() and token == os.environ.get("EDGE_TOKEN", "dev-edge-token"):
            return True                       # simulator / demo only
        entry = self._load().get(station_id)
        return bool(entry) and hmac.compare_digest(entry["hash"], hashlib.sha256(token.encode()).hexdigest())
