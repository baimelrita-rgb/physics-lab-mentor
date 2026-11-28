"""MVP package 2: lesson lifecycle. Unique codes, end lesson, auto-close, groups may finish."""
import pytest
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.auth import Auth
from lab.roster import Roster


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))
    monkeypatch.setattr(appmod, "ROSTER", Roster(tmp_path))
    return TestClient(appmod.app)


def test_codes_unique_among_open_lessons(c, monkeypatch):
    seq = iter([123456, 123456, 123456, 654321])
    monkeypatch.setattr("secrets.randbelow", lambda n: next(seq))
    a = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()["lesson"]["code"]
    b = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()["lesson"]["code"]
    assert a == "123456" and b == "654321"


def test_end_lesson_blocks_new_joins_but_groups_finish(c):
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "class_name": "י׳1"}).json()
    lid, code = live["lesson"]["id"], live["lesson"]["code"]
    c.post("/api/teacher/roster", json={"class_name": "י׳1", "names": ["נועה"]})
    sid = c.post("/api/join", json={"code": code, "label": "א"}).json()["id"]
    after = c.post(f"/api/teacher/lessons/{lid}/close").json()
    assert after["lesson"]["closed"] is True
    assert c.post("/api/join", json={"code": code, "label": "ב"}).status_code == 404
    assert c.get(f"/api/join/{code}").status_code == 404                  # names no longer exposed
    assert c.post(f"/api/sessions/{sid}/theory", json={"choice": 0}).status_code == 200   # may finish
    assert appmod.LESSONS[lid].closed_at > 0


def test_lesson_closes_automatically(c, monkeypatch):
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()
    lesson = appmod.LESSONS[live["lesson"]["id"]]
    lesson.started -= (appmod.LESSON_HOURS + 1) * 3600
    assert c.post("/api/join", json={"code": lesson.code, "label": "x"}).status_code == 404
    assert lesson.closed and lesson.closed_at == pytest.approx(lesson.started + appmod.LESSON_HOURS * 3600)


def test_planned_lesson_is_not_auto_closed(c):
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "planned": True}).json()
    lesson = appmod.LESSONS[live["lesson"]["id"]]
    lesson.started -= 100 * 3600
    c.get("/api/teacher/lessons")
    assert not lesson.closed
