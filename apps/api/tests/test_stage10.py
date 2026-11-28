"""Stage 10: content editing with the answer wall enforced, approval and revert."""
import pytest
from fastapi.testclient import TestClient

from lab import app as appmod, content
from lab.auth import Auth


@pytest.fixture
def c(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))
    content.reload()
    yield TestClient(appmod.app)
    content.reload()


def test_leak_term_blocked_in_student_text(c):
    r = c.put("/api/teacher/content/EX-01", json={"changes": {"goal": "להבין שהייתה תוספת עומס"}}).json()
    assert r["saved"] is False and r["errors"][0]["path"] == "goal"
    # The same words are fine in a teacher-only field.
    assert c.put("/api/teacher/content/EX-01", json={"changes": {"subtitle": "תוספת עומס"}}).json()["saved"]


def test_edit_reaches_students_and_returns_to_draft(c):
    hints = ["האם המהירות לבדה מספיקה?", "מה עשה תדר היציאה?", "מה עשה המומנט?"]
    r = c.put("/api/teacher/content/EX-01", json={"changes": {"hints": hints}}).json()
    assert r["saved"] and r["changed"] == ["hints"]
    assert content.exercises()["exercises"]["EX-01"]["hints"] == hints
    assert r["exercise"]["status"] == "draft"
    assert c.post("/api/teacher/content/EX-01/approve").json()["status"] == "approved"
    hist = c.get("/api/teacher/content/EX-01").json()["history"]
    assert hist[0]["field"] == "status" and hist[1]["field"] == "hints" and hist[1]["by"] == "מצב הדגמה"
    assert "hints:" in c.get("/api/teacher/content/export.yaml").text
    # Revert goes back to the repository text and status.
    back = c.post("/api/teacher/content/EX-01/revert").json()
    assert back["status"] == "approved" and content.exercises()["exercises"]["EX-01"]["hints"] != hints


def test_rules(c):
    bad = c.put("/api/teacher/content/EX-01", json={"changes": {"hints": ["א?", "ב."]}}).json()
    msgs = " ".join(e["message"] for e in bad["errors"])
    assert "שלושה" in msgs and "שאלה" in msgs
    assert not c.put("/api/teacher/content/EX-01", json={"changes": {"check_answer": 7}}).json()["saved"]
    assert c.put("/api/teacher/content/EX-01", json={"changes": {"recording": "E01"}}).status_code == 422
    # Draft content with a hint that is not a question cannot be approved.
    assert c.post("/api/teacher/content/EX-04/approve").status_code == 409


def test_student_api_follows_edits_but_never_key(c):
    c.put("/api/teacher/content/EX-01", json={"changes": {"exit_question": "מה למדתם על החלקה?"}})
    v = c.post("/api/sessions", json={"exercise_id": "EX-01"}).json()
    assert "conclusion" not in str(v) and "leak_terms" not in str(v)
