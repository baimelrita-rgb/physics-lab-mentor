"""MVP package 5: a session keeps the content version it started with."""
from lab import content, teacher
from lab.ingest import load_all, resolve
from lab.session import Session
from lab.store import Store


def _session():
    return Session("EX-01", resolve(load_all(content.DATA), "E03"))


def test_edit_mid_lesson_does_not_change_running_session(monkeypatch):
    s = _session()
    v0, goal0, ans0 = s.content_version, s.ex["goal"], s.key["check_answer"]
    real_ex, real_key = content.exercises(), content.answer_key()
    edited_ex = {**real_ex, "exercises": {**real_ex["exercises"],
                 "EX-01": {**real_ex["exercises"]["EX-01"], "goal": "מטרה חדשה"}}}
    edited_key = {**real_key, "EX-01": {**real_key["EX-01"], "check_answer": ans0 + 1}}
    monkeypatch.setattr(content, "exercises", lambda: edited_ex)
    monkeypatch.setattr(content, "answer_key", lambda: edited_key)
    assert s.ex["goal"] == goal0 and s.key["check_answer"] == ans0 and s.content_version == v0
    assert s.answer_theory(ans0)                    # graded by the pinned key
    new = _session()
    assert new.ex["goal"] == "מטרה חדשה" and new.content_version != v0


def test_pinned_version_survives_restart_and_is_in_csv(tmp_path):
    s = _session()
    store = Store(tmp_path)
    store.save_session(s)
    loaded = store.load(load_all(content.DATA), log_path=None, replay_speed=1, tutor=None)[0][s.id]
    assert loaded.pinned == s.pinned
    lesson = teacher.Lesson("EX-01")
    lesson.session_ids.append(s.id)
    csv = teacher.export_csv(lesson, {s.id: s})
    assert "גרסת תוכן" in csv and s.content_version in csv
