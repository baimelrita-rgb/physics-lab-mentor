"""Stage 6: teacher accounts, login, lockout and lesson ownership."""
import json

import pytest
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.auth import COOKIE, Auth, AuthError


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def test_password_stored_only_as_hash(tmp_path):
    a = Auth(tmp_path)
    a.add_teacher("rita", "ריטה", "correct horse")
    raw = (tmp_path / "teachers.json").read_text(encoding="utf-8")
    assert "correct horse" not in raw and "hash" in raw
    assert (tmp_path / "teachers.json").stat().st_mode & 0o077 == 0
    with pytest.raises(AuthError):
        a.add_teacher("x", "x", "short")


def test_login_cookie_tamper_and_expiry(tmp_path):
    clock = Clock()
    a = Auth(tmp_path, clock=clock)
    a.add_teacher("rita", "ריטה", "correct horse")
    cookie = a.login("Rita", "correct horse")
    assert a.user_from_cookie(cookie) == "rita"
    body, sig = cookie.rsplit(".", 1)
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + sig
    assert a.user_from_cookie(forged) is None
    assert a.user_from_cookie(cookie[:-1] + ("0" if cookie[-1] != "0" else "1")) is None
    clock.t += 13 * 3600
    assert a.user_from_cookie(cookie) is None


def test_lockout_after_five_failures(tmp_path):
    clock = Clock()
    a = Auth(tmp_path, clock=clock)
    a.add_teacher("rita", "ריטה", "correct horse")
    for _ in range(5):
        with pytest.raises(AuthError, match="wrong"):
            a.login("rita", "nope")
    with pytest.raises(AuthError, match="locked"):
        a.login("rita", "correct horse")          # even the right password while locked
    clock.t += 301
    assert a.login("rita", "correct horse")


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    a = Auth(tmp_path)
    a.add_teacher("rita", "ריטה", "password-rita")
    a.add_teacher("dana", "דנה", "password-dana")
    monkeypatch.setattr(appmod, "AUTH", a)
    return a


def client_for(user, pw):
    c = TestClient(appmod.app)
    r = c.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200 and COOKIE in r.cookies
    return c


def test_teacher_api_requires_login(accounts):
    c = TestClient(appmod.app)
    assert c.get("/api/teacher/lessons").status_code == 401
    assert c.get("/api/auth/me").status_code == 401
    assert c.post("/api/auth/login", json={"username": "rita", "password": "bad"}).status_code == 401
    rita = client_for("rita", "password-rita")
    assert rita.get("/api/auth/me").json() == {"user": "rita", "name": "ריטה", "demo": False}
    rita.post("/api/auth/logout")
    assert rita.get("/api/teacher/lessons").status_code == 401


def test_teacher_sees_only_own_lessons(accounts):
    rita, dana = client_for("rita", "password-rita"), client_for("dana", "password-dana")
    live = rita.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()
    lid, code = live["lesson"]["id"], live["lesson"]["code"]
    sid = TestClient(appmod.app).post("/api/join", json={"code": code, "label": "קבוצה ד"}).json()["id"]
    assert lid in [l["id"] for l in rita.get("/api/teacher/lessons").json()]
    assert lid not in [l["id"] for l in dana.get("/api/teacher/lessons").json()]
    assert dana.get(f"/api/teacher/lessons/{lid}").status_code == 404
    assert dana.get(f"/api/teacher/sessions/{sid}").status_code == 404
    assert dana.post(f"/api/teacher/sessions/{sid}/pause").status_code == 404
    assert dana.get(f"/api/teacher/lessons/{lid}/export.csv").status_code == 404
    assert rita.get(f"/api/teacher/sessions/{sid}").status_code == 200
    # Students need no login.
    assert TestClient(appmod.app).get(f"/api/sessions/{sid}").status_code == 200


def test_demo_mode_without_accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))
    c = TestClient(appmod.app)
    assert c.get("/api/auth/me").json()["demo"] is True
    assert c.get("/api/teacher/lessons").status_code == 200
    assert json.dumps(c.get("/api/teacher/exercises").json(), ensure_ascii=False)
