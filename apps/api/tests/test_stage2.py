import json

import pytest
from fastapi.testclient import TestClient

from lab import app as appmod
from lab import teacher
from lab.session import GuardError
from test_stage1 import _to_evidence, new, recs  # noqa: F401  (fixture reuse)


def test_pause_freezes_replay_and_blocks_actions(recs):
    s, clock = new(recs)
    s.advance(); s.submit_prediction({"speed_rpm": "down"}); s.advance()
    clock.t = 5
    s.pause()
    clock.t = 15
    assert s.visible_t() == 5
    with pytest.raises(GuardError):
        s.open_channel("f_drive_hz")
    s.resume()
    clock.t = 17
    assert s.visible_t() == 7


def test_teacher_hint_counts_and_is_marked(recs):
    s, clock = _to_evidence(recs)
    s.teacher_hint()
    v = s.student_view()
    assert v["hints"]["used"] == 1 and v["hints"]["sources"] == ["teacher"]


def test_stuck_alert_and_card_order(recs, monkeypatch):
    monkeypatch.setattr(teacher, "STUCK_SECONDS", 60)
    a, ca = _to_evidence(recs)
    b, cb = _to_evidence(recs)
    a.label, b.label = "עמדה 1", "עמדה 2"
    cb.t += 120                                   # station 2 sits in EVIDENCE for 2 minutes
    lesson = teacher.Lesson("EX-01")
    lesson.session_ids = [a.id, b.id]
    live = teacher.live(lesson, {a.id: a, b.id: b})
    assert [c["label"] for c in live["cards"]] == ["עמדה 2", "עמדה 1"]
    assert live["cards"][0]["flag"] == "תקוע"
    assert live["alerts"][0]["suggest"]


def test_rubric_full_marks_path(recs):
    s, clock = _to_evidence(recs)
    s.open_channel("f_drive_hz"); s.open_channel("torque_nm")
    ids = [s.add_reading("f_drive_hz", 5)["id"], s.add_reading("f_drive_hz", 20)["id"],
           s.add_reading("torque_nm", 20)["id"]]
    s.advance(); s.submit_reason("התדר נשאר והמומנט עלה", ids)
    clock.t = 60; s.add_reading("torque_nm", 30); s.advance(); s.submit_exit("כן")
    assert teacher.rubric(s) == [2, 2, 2, 2]


def test_misconception_counted(recs):
    s, clock = _to_evidence(recs, "H-FREQ")
    ids = [s.add_reading("speed_rpm", 5)["id"], s.add_reading("speed_rpm", 20)["id"]]
    s.advance(); s.submit_reason("התדר ירד", ids)
    assert teacher.misconceptions_of(s) == ["M-01"]


def test_api_lesson_join_and_answer_wall():
    c = TestClient(appmod.app)
    live = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01"}).json()
    code, lid = live["lesson"]["code"], live["lesson"]["id"]
    st = c.post("/api/join", json={"code": code, "label": "קבוצה א"}).json()
    assert st["label"] == "קבוצה א"
    assert c.post("/api/join", json={"code": "000000x", "label": "x"}).status_code == 404
    cards = c.get(f"/api/teacher/lessons/{lid}").json()["cards"]
    assert cards[0]["id"] == st["id"]
    det = c.get(f"/api/teacher/sessions/{st['id']}").json()
    assert det["expected"]["cause"] == "H-LOAD"            # teacher sees the key
    student = json.dumps(c.get(f"/api/sessions/{st['id']}").json(), ensure_ascii=False)
    for secret in ("expected", "cause", "תוספת עומס", "conclusion"):  # student does not
        assert secret not in student
    c.post(f"/api/teacher/lessons/{lid}/pause")
    assert c.get(f"/api/sessions/{st['id']}").json()["paused"] is True
    c.post(f"/api/teacher/sessions/{st['id']}/message", json={"text": "בדקו את תדר היציאה"})
    assert c.get(f"/api/sessions/{st['id']}").json()["note_from_teacher"] == "בדקו את תדר היציאה"


def test_state_survives_restart(recs, tmp_path):
    from lab.store import Store
    s, clock = _to_evidence(recs)
    s.label = "קבוצה ב"
    s.open_channel("torque_nm")
    s.add_reading("torque_nm", 20)
    s.request_hint()
    lesson = teacher.Lesson("EX-01")
    lesson.session_ids.append(s.id)
    store = Store(tmp_path)
    store.save_session(s)
    store.save_lesson(lesson)

    sessions, lessons = Store(tmp_path).load(recs, log_path=None, replay_speed=1, tutor=None)
    s2 = sessions[s.id]
    assert (s2.state, s2.label, s2.hypothesis, s2.hints_used) == ("EVIDENCE", "קבוצה ב", "H-LOAD", 1)
    assert s2.readings == s.readings and s2.open_channels == s.open_channels
    assert s2.add_reading("torque_nm", 5)["id"] == "r2"      # ids continue, no collision
    assert lessons[lesson.id].code == lesson.code and lessons[lesson.id].session_ids == [s.id]


def test_envelope_only_in_overload_recording(recs):
    from lab import envelope
    from lab.ingest import resolve
    hits = {name: envelope.for_recording(resolve(recs, name)) for name in
            ["E01", "E02", "E03", "E04", "N01_25HZ", "N02_50HZ", "N03_LOAD_STEP"]}
    assert all(not v for k, v in hits.items() if k != "E04")
    stops = {(e["rule"], e["t"]) for e in hits["E04"] if e["level"] == "stop"}
    assert stops == {("R-MOT-01", 16), ("R-MOT-02", 16)}


def test_safety_alert_first_and_hidden_from_student(recs):
    from test_stage1 import new
    s, clock = new(recs, "EX-04")
    s.advance(); s.submit_prediction({"torque_nm": "up"}); s.advance()
    clock.t = 10
    assert not [a for a in teacher.alerts(s) if a["kind"] == "safety"]   # second 10: not yet
    clock.t = 100
    al = teacher.alerts(s)
    assert al[0]["kind"] == "safety" and "R-MOT" in al[0]["title"]
    lesson = teacher.Lesson("EX-04"); lesson.session_ids = [s.id]
    assert teacher.live(lesson, {s.id: s})["cards"][0]["flag"] == "בטיחות"
    assert "R-MOT" not in json.dumps(s.student_view())
