"""MVP package 4: tenant -> lab -> station ownership; per-tenant content; content approver role."""
import sqlite3
import threading

import pytest
from fastapi.testclient import TestClient

from lab import app as appmod, content
from lab.auth import COOKIE, Auth, AuthError
from lab.live import LiveStation
from lab.org import Org, OrgError


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    a = Auth(tmp_path)
    a.add_teacher("rita", "ריטה", "password-rita", tenant="school-a", labs=["lab-a1"])
    a.add_teacher("noa", "נועה", "password-noa", tenant="school-a", role="content_admin")
    a.add_teacher("dana", "דנה", "password-dana", tenant="school-b")
    monkeypatch.setattr(appmod, "AUTH", a)
    org = Org(sqlite3.connect(":memory:", check_same_thread=False), threading.Lock())
    for t in ("school-a", "school-b"):
        org.add_tenant(t, t)
    org.add_lab("lab-a1", "school-a", "A1")
    org.add_lab("lab-a2", "school-a", "A2")
    org.add_lab("lab-b1", "school-b", "B1")
    org.assign_station("ST-A1", "lab-a1")
    org.assign_station("ST-A2", "lab-a2")
    org.assign_station("ST-B1", "lab-b1")
    monkeypatch.setattr(appmod, "ORG", org)
    for sid in ("ST-A1", "ST-A2", "ST-B1"):
        monkeypatch.setitem(appmod.STATIONS, sid, LiveStation(sid))
    content.reload()
    yield
    content.reload()


def login(user, pw):
    c = TestClient(appmod.app)
    assert c.post("/api/auth/login", json={"username": user, "password": pw}).status_code == 200
    return c


def lesson(c):
    r = c.post("/api/teacher/lessons", json={"exercise_id": "EX-01", "setup_ack": True})
    assert r.status_code == 200
    return r.json()["lesson"]


def test_lessons_and_sessions_never_cross_tenants(world):
    rita, dana = login("rita", "password-rita"), login("dana", "password-dana")
    lb = lesson(dana)
    assert appmod.LESSONS[lb["id"]].tenant_id == "school-b"
    assert rita.get(f"/api/teacher/lessons/{lb['id']}").status_code == 404
    assert lb["id"] not in [l["id"] for l in rita.get("/api/teacher/lessons").json()]
    s = TestClient(appmod.app).post("/api/join", json={"code": lb["code"], "label": "g"}).json()
    assert appmod.SESSIONS[s["id"]].tenant_id == "school-b"
    assert rita.get(f"/api/teacher/sessions/{s['id']}").status_code == 404
    assert dana.get(f"/api/teacher/sessions/{s['id']}").status_code == 200


def test_stations_filtered_by_tenant_and_lab(world):
    rita, noa, dana = login("rita", "password-rita"), login("noa", "password-noa"), login("dana", "password-dana")
    names = lambda c: {x["station"] for x in c.get("/api/teacher/stations").json()}
    assert names(rita) == {"ST-A1"}                  # rita is limited to lab-a1
    assert names(noa) == {"ST-A1", "ST-A2"}          # whole tenant
    assert names(dana) == {"ST-B1"}
    assert dana.get("/api/teacher/stations/ST-A1/monitor").status_code == 404


def test_content_edits_stay_in_their_tenant(world):
    rita, dana = login("rita", "password-rita"), login("dana", "password-dana")
    assert rita.put("/api/teacher/content/EX-01", json={"changes": {"goal": "מטרה של בית ספר א"}}).json()["saved"]
    assert rita.get("/api/teacher/content/EX-01").json()["status"] == "draft"
    goal = lambda c: next(f["value"] for f in c.get("/api/teacher/content/EX-01").json()["fields"] if f["path"] == "goal")
    assert goal(rita) == "מטרה של בית ספר א" and goal(dana) != "מטרה של בית ספר א"
    with content.use_tenant("default"):
        assert content.exercises()["exercises"]["EX-01"]["goal"] != "מטרה של בית ספר א"
    # A lesson of school-a pins school-a's text.
    la = lesson(rita)
    s = TestClient(appmod.app).post("/api/join", json={"code": la["code"], "label": "g"}).json()
    assert appmod.SESSIONS[s["id"]].ex["goal"] == "מטרה של בית ספר א"
    assert appmod.SESSIONS[s["id"]].pinned["tenant"] == "school-a"


def test_only_content_admin_approves_when_tenant_has_one(world):
    rita, noa, dana = login("rita", "password-rita"), login("noa", "password-noa"), login("dana", "password-dana")
    rita.put("/api/teacher/content/EX-01", json={"changes": {"subtitle": "שינוי"}})
    assert rita.post("/api/teacher/content/EX-01/approve").status_code == 403
    assert noa.post("/api/teacher/content/EX-01/approve").json()["status"] == "approved"
    # school-b has no content admin: its teachers approve their own edits.
    dana.put("/api/teacher/content/EX-01", json={"changes": {"subtitle": "שינוי ב"}})
    assert dana.post("/api/teacher/content/EX-01/approve").status_code == 200
    assert rita.get("/api/auth/me").json()["can_approve"] is False


def test_account_and_org_validation(tmp_path):
    a = Auth(tmp_path)
    a.add_teacher("rita", "ריטה", "password-rita", tenant="school-a")
    with pytest.raises(AuthError):
        a.add_teacher("rita", "ריטה", "password-rita", tenant="school-b")     # usernames do not move tenants
    with pytest.raises(AuthError):
        a.add_teacher("x", "x", "password-xx", tenant="Bad Tenant")
    org = Org(sqlite3.connect(":memory:"), threading.Lock())
    org.add_tenant("t1", "t1")
    org.add_tenant("t2", "t2")
    org.add_lab("lab", "t1", "L")
    with pytest.raises(OrgError):
        org.add_lab("lab", "t2", "L")                 # a lab id cannot be taken over by another tenant
    assert org.station("never-assigned")["tenant"] == "default"
