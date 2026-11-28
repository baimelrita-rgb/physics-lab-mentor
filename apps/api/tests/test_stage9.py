"""Stage 9: class roster, group members on join, per-student view."""
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.auth import Auth
from lab.roster import Roster


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "AUTH", Auth(tmp_path))        # demo mode
    monkeypatch.setattr(appmod, "ROSTER", Roster(tmp_path))
    return TestClient(appmod.app)


def test_roster_file_private_and_no_duplicates(tmp_path):
    r = Roster(tmp_path)
    r.add("", "י׳1", ["נועה כ.", "נועה כ.", "  עומר   ל. ", ""])
    assert [s["name"] for s in r.students("", "י׳1")] == ["נועה כ.", "עומר ל."]
    assert (tmp_path / "rosters.json").stat().st_mode & 0o077 == 0
    assert r.students("rita", "י׳1") == []                         # another teacher's roster is separate


def test_join_with_members_and_student_view(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    ids = [s["id"] for s in c.post("/api/teacher/roster", json={"class_name": "י׳1", "names": ["נועה כ.", "עומר ל.", "דנה ש."]}).json()]
    code = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "class_name": "י׳1"}).json()["lesson"]["code"]
    info = c.get(f"/api/join/{code}").json()
    assert [x["name"] for x in info["roster"]] == ["נועה כ.", "עומר ל.", "דנה ש."]
    assert c.post("/api/join", json={"code": code, "label": "א", "members": ["st_nope"]}).status_code == 422
    sid = c.post("/api/join", json={"code": code, "label": "א", "members": ids[:2]}).json()["id"]
    assert [x["taken"] for x in c.get(f"/api/join/{code}").json()["roster"]] == [True, True, False]
    ov = c.get("/api/teacher/students", params={"class_name": "י׳1"}).json()
    assert [s["lessons"] for s in ov["students"]] == [1, 1, 0]
    d = c.get(f"/api/teacher/students/{ids[0]}", params={"class_name": "י׳1"}).json()
    assert d["sessions"][0]["partners"] == ["עומר ל."]
    # The teacher fixes the group: Dana was there too.
    c.post(f"/api/teacher/sessions/{sid}/members", json={"members": ids})
    assert c.get("/api/teacher/students", params={"class_name": "י׳1"}).json()["students"][2]["lessons"] == 1
    # A student who left is hidden from the join screen but keeps the history.
    c.patch(f"/api/teacher/roster/{ids[2]}", json={"class_name": "י׳1", "active": False})
    assert len(c.get(f"/api/join/{code}").json()["roster"]) == 2
    assert c.get(f"/api/teacher/students/{ids[2]}", params={"class_name": "י׳1"}).json()["sessions"]
    # Roster-only class appears in the class list.
    c.post("/api/teacher/roster", json={"class_name": "י׳3", "names": ["רון"]})
    assert {"name": "י׳3", "lessons": 0} in c.get("/api/teacher/classes").json()


def test_student_api_has_no_roster_data(tmp_path, monkeypatch):
    c = setup(tmp_path, monkeypatch)
    ids = [s["id"] for s in c.post("/api/teacher/roster", json={"class_name": "י׳1", "names": ["נועה כ."]}).json()]
    code = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "class_name": "י׳1"}).json()["lesson"]["code"]
    v = c.post("/api/join", json={"code": code, "label": "א", "members": ids}).json()
    assert "members" not in v and "נועה" not in str(v)
