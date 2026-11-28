"""MVP package 3: access protection."""
import csv
import io

import pytest
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.auth import Auth
from lab.roster import Roster
from lab.security import RateLimiter, StationTokens, csv_safe


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))
    monkeypatch.setattr(appmod, "ROSTER", Roster(tmp_path))
    monkeypatch.setattr(appmod, "JOIN_FAILS", RateLimiter(20, 600))
    return TestClient(appmod.app)


def lesson(c):
    return c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()["lesson"]


def test_session_answers_only_to_its_tablet(c):
    tablet = TestClient(appmod.app)
    sid = tablet.post("/api/join", json={"code": lesson(c)["code"], "label": "א"}).json()["id"]
    other = TestClient(appmod.app)
    assert other.get(f"/api/sessions/{sid}").status_code == 403
    assert other.post(f"/api/sessions/{sid}/theory", json={"choice": 0}).status_code == 403
    assert tablet.post(f"/api/sessions/{sid}/theory", json={"choice": 0}).status_code == 200
    assert "token" not in tablet.get(f"/api/sessions/{sid}").json()


def test_teacher_moves_group_to_another_tablet(c):
    tablet = TestClient(appmod.app)
    sid = tablet.post("/api/join", json={"code": lesson(c)["code"], "label": "א"}).json()["id"]
    c.post(f"/api/teacher/sessions/{sid}/release")
    new = TestClient(appmod.app)
    assert new.get(f"/api/sessions/{sid}").status_code == 200          # claims it
    assert tablet.get(f"/api/sessions/{sid}").status_code == 403       # old tablet is out


def test_wrong_codes_are_rate_limited_per_ip(c):
    for _ in range(20):
        assert c.post("/api/join", json={"code": "000000", "label": "x"}).status_code in (404, 429)
    assert c.post("/api/join", json={"code": "000000", "label": "x"}).status_code == 429


def test_successful_joins_are_not_limited(c):
    code = lesson(c)["code"]
    for i in range(40):                     # a whole school behind one IP
        assert TestClient(appmod.app).post("/api/join", json={"code": code, "label": f"g{i}"}).status_code == 200


def test_no_accounts_without_demo_flag_is_locked(c, monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO", "0")
    assert c.get("/api/teacher/lessons").status_code == 401
    assert c.post("/api/sessions", json={"exercise_id": "EX-01"}).status_code == 403
    assert c.get("/api/status").json()["demo"] is False


def test_cross_site_post_refused(c):
    r = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"},
                  headers={"Origin": "http://testserver"}).status_code == 200


def test_csv_formulas_neutralized(c):
    l = lesson(c)
    TestClient(appmod.app).post("/api/join", json={"code": l["code"], "label": "=HYPERLINK(\"x\")"})
    rows = list(csv.reader(io.StringIO(c.get(f"/api/teacher/lessons/{l['id']}/export.csv").text.lstrip("﻿"))))
    assert rows[1][0].startswith("'=")
    assert csv_safe("-1") == "'-1" and csv_safe(3) == 3


def test_station_tokens(tmp_path, monkeypatch):
    t = StationTokens(tmp_path)
    tok = t.issue("ST-1")
    assert t.valid("ST-1", tok) and not t.valid("ST-2", tok) and not t.valid("ST-1", "nope")
    assert tok not in (tmp_path / "stations.json").read_text()
    monkeypatch.setenv("DEMO", "0")
    assert not t.valid("ST-1", "dev-edge-token")
