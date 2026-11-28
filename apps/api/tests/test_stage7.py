"""Stage 7: lesson prep wizard. Settings chosen by the teacher reach every station that joins."""
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.auth import Auth


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))      # demo mode
    return TestClient(appmod.app)


def test_preview_has_student_view_and_key(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    p = c.get("/api/teacher/prep/EX-01").json()
    assert p["number"] == "תרגיל 1" and p["title"] == "האטה בציר"
    assert len(p["student"]["hints"]) == 3 and p["key"]["cause"]
    assert all(r["status"] for r in p["setup"]["envelope"])
    assert c.get("/api/teacher/prep/EX-99").status_code == 404
    st = c.get("/api/teacher/prep/stations").json()
    assert st[0]["usable"] and st[0]["mode"] == "recording"


def test_settings_reach_station(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "class_name": "י׳2", "date": "2026-12-01",
                                                "stations": 4, "hint_quota": 1, "allow_ask": False,
                                                "deduction": "per_hint"}).json()
    code = live["lesson"]["code"]
    s = c.post("/api/join", json={"code": code, "label": "קבוצה א"}).json()
    assert s["hints"]["quota"] == 1 and s["can_ask"] is False
    lessons = {l["id"]: l for l in c.get("/api/teacher/lessons").json()}
    assert lessons[live["lesson"]["id"]]["class_name"] == "י׳2"


def test_invalid_settings_and_unconfirmed_setup(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "hint_quota": 9}).status_code == 422
    assert c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "deduction": "x"}).status_code == 422
    assert c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "setup_ack": False}).status_code == 409


def test_planned_lesson_is_closed_to_students_until_opened(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "planned": True}).json()
    lid, code = live["lesson"]["id"], live["lesson"]["code"]
    assert c.post("/api/join", json={"code": code, "label": "א"}).status_code == 404
    c.post(f"/api/teacher/lessons/{lid}/open")
    assert c.post("/api/join", json={"code": code, "label": "א"}).status_code == 200
    assert c.post(f"/api/teacher/lessons/{lid}/explode").status_code == 404


def test_deduction_lowers_total(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "deduction": "per_hint"}).json()
    sid = c.post("/api/join", json={"code": live["lesson"]["code"], "label": "א"}).json()["id"]
    s = appmod.SESSIONS[sid]
    s.hint_sources = ["student", "teacher"]
    card = c.get(f"/api/teacher/lessons/{live['lesson']['id']}").json()["cards"][0]
    assert card["deduction"] == 1                                   # teacher hints are not deducted
    assert "ניכוי רמזים" in c.get(f"/api/teacher/lessons/{live['lesson']['id']}/export.csv").text
