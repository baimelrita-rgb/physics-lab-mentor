"""HTTP API (technical design §7, the student part). Run: uvicorn lab.app:app"""
from __future__ import annotations

import os
import threading
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import classview, content, editor, envelope, llm, setup, students, teacher
from .roster import Roster, RosterError
from .ingest import load_all, resolve
from .live import FrameError, LiveStation
from .session import GuardError, Session, exercise_number
from .teacher import Lesson
from .auth import COOKIE, DEMO_USER, Auth, AuthError
from .store import Store
from .security import (SESSION_COOKIE, RateLimiter, StationTokens, client_ip, cookie_secure, demo_mode,
                       new_token)
from .tutor import Tutor

app = FastAPI(title="Lab Mentor")
RECORDINGS = load_all(content.DATA)
TUTOR = Tutor()
LOG = content.ROOT / "var" / "learning_log.jsonl"
SPEED = float(os.environ.get("REPLAY_SPEED", "1"))
STORE = Store(Path(os.environ.get("STATE_DIR", content.ROOT / "var" / "state")))
# Sessions and lessons survive a server restart.
SESSIONS, LESSONS = STORE.load(RECORDINGS, log_path=LOG, replay_speed=SPEED, tutor=TUTOR)


def _session(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "session not found")
    return s


# One lock per session: two tablets of the same group, or a double tap, are applied one
# after the other instead of interleaving (QA finding F-01).
_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)
_LOCKS_GUARD = threading.Lock()


@contextmanager
def session_lock(sid: str):
    with _LOCKS_GUARD:
        lock = _LOCKS[sid]
    with lock:
        yield


# ---------- access protection (MVP package 3) ----------
JOIN_FAILS = RateLimiter(20, 600)        # wrong lesson codes per IP per 10 minutes
LOGIN_FAILS = RateLimiter(20, 600)       # wrong passwords per IP per 10 minutes
ANON_SESSIONS = RateLimiter(30, 3600)    # practice sessions without a lesson, per IP per hour


def _set_group_cookie(resp, s: Session):
    resp.set_cookie(SESSION_COOKIE, s.token, path=f"/api/sessions/{s.id}", httponly=True, samesite="lax",
                    secure=cookie_secure(), max_age=12 * 3600)
    return resp


@app.middleware("http")
async def guard(request: Request, call_next):
    path = request.url.path
    # Requests from another site's page are refused (CSRF); the edge agent is not a browser.
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and path.startswith("/api/") \
            and not path.startswith("/api/edge/"):
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlparse
            if urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
    # A group's session answers only to the tablet that holds its token (QA finding F-05).
    if path.startswith("/api/sessions/"):
        sid = path.split("/")[3]
        s = SESSIONS.get(sid)
        if s is not None:
            if s.token and request.cookies.get(SESSION_COOKIE) != s.token:
                return JSONResponse({"detail": "this station belongs to another device"}, status_code=403)
            if not s.token:                     # released by the teacher, or created before tokens: claim it
                s.token = new_token()
                STORE.save_session(s)
                return _set_group_cookie(await call_next(request), s)
    return await call_next(request)


def _run(sid: str, fn):
    s = _session(sid)
    with session_lock(sid):
        try:
            fn(s)
        except GuardError as e:
            raise HTTPException(409, {"code": "STATE_GUARD_FAILED", "detail": str(e)})
        finally:
            STORE.save_session(s)
        return s.student_view()


class NewSession(BaseModel):
    exercise_id: str
    label: str = "עמדה 1"


class Join(BaseModel):
    code: str
    label: str = "עמדה"
    members: list[str] = []


class RosterAdd(BaseModel):
    class_name: str
    names: list[str]


class RosterEdit(BaseModel):
    class_name: str
    name: str | None = None
    active: bool | None = None


class Members(BaseModel):
    members: list[str]


class NewLesson(BaseModel):
    exercise_id: str
    class_name: str = ""
    date: str = ""
    stations: int = 1
    hint_quota: int = 3
    allow_ask: bool = True
    deduction: str = "none"
    planned: bool = False
    setup_ack: bool = True


class Scores(BaseModel):
    scores: list[int]
    note: str = ""


class Choice(BaseModel):
    choice: int


class Prediction(BaseModel):
    directions: dict[str, str] = {}
    text: str = ""


class Code(BaseModel):
    code: str


class OpenChannel(BaseModel):
    expectation: str | None = None


class ReadingIn(BaseModel):
    channel: str
    t: int


class Reason(BaseModel):
    text: str = ""
    cited: list[str] = []


class Text(BaseModel):
    text: str


@app.get("/api/exercises")
def list_exercises():
    """Public list: numbers only. Exercise names can reveal the answer, so only the teacher sees them."""
    exs = content.exercises()["exercises"]
    return [{"id": k, "number": exercise_number(k), "status": v["status"],
             "available": resolve(RECORDINGS, v["recording"]) is not None} for k, v in exs.items()]


def _new_session(exercise_id: str, label: str, lesson: Lesson | None = None, members: list[str] | None = None) -> Session:
    ex = content.exercises()["exercises"].get(exercise_id)
    rec = resolve(RECORDINGS, ex["recording"]) if ex else None
    if not rec:
        raise HTTPException(404, "exercise or recording not available")
    s = Session(exercise_id, rec, log_path=LOG, replay_speed=SPEED, token=new_token(),
                label=label.strip()[:30] or "עמדה", lesson_id=lesson.id if lesson else None, tutor=TUTOR)
    if lesson:
        s.hint_quota, s.allow_ask = lesson.hint_quota, lesson.allow_ask
        s.members = list(members or [])
    SESSIONS[s.id] = s
    STORE.save_session(s)
    if lesson:
        lesson.session_ids.append(s.id)
        STORE.save_lesson(lesson)
    return s


@app.post("/api/sessions")
def create_session(body: NewSession, request: Request):
    """Practice without a lesson: only in demo mode or for a logged-in teacher (QA finding F-07)."""
    if not (AUTH.demo or AUTH.user_from_cookie(request.cookies.get(COOKIE))):
        raise HTTPException(403, "practice without a lesson needs a teacher login")
    ip = client_ip(request)
    if ANON_SESSIONS.blocked(ip):
        raise HTTPException(429, "too many practice sessions")
    ANON_SESSIONS.hit(ip)
    s = _new_session(body.exercise_id, body.label)
    return _set_group_cookie(JSONResponse(s.student_view()), s)


@app.post("/api/join")
def join(body: Join, request: Request):
    lesson = _code_lesson(body.code, request)
    s = _new_session(lesson.exercise_id, body.label, lesson, _valid_members(lesson, body.members))
    return _set_group_cookie(JSONResponse(s.student_view()), s)


def _code_lesson(code: str, request: Request) -> Lesson:
    """Lesson by code, with a limit on wrong codes per IP (QA finding F-04)."""
    ip = client_ip(request)
    if JOIN_FAILS.blocked(ip):
        raise HTTPException(429, "too many wrong codes, try again in a few minutes")
    try:
        return _open_lesson(code)
    except HTTPException:
        JOIN_FAILS.hit(ip)
        raise


ROSTER = Roster(STORE.root)


def _names(lesson: Lesson) -> dict[str, str]:
    return {x["id"]: x["name"] for x in ROSTER.students(lesson.owner, lesson.class_name)}


def _live(lesson: Lesson, sessions: dict) -> dict:
    """Live lesson view plus the names of each group's students (from the class roster)."""
    out = teacher.live(lesson, sessions)
    names = _names(lesson)
    for c in out["cards"]:
        c["member_names"] = [names.get(m, "?") for m in c.get("members", [])]
    out["lesson"]["class_name"] = lesson.class_name
    return out


def _detail(s: Session) -> dict:
    out = teacher.detail(s)
    lesson = LESSONS.get(s.lesson_id) if s.lesson_id else None
    out["members"] = s.members
    out["roster"] = [{"id": x["id"], "name": x["name"]}
                     for x in ROSTER.students(lesson.owner, lesson.class_name, active_only=True)] if lesson else []
    return out


# Lesson lifecycle (MVP package 2). A lesson ends when the teacher ends it, or automatically
# LESSON_HOURS after it started. Ending stops new joins and frees the code; groups that are
# still working may finish their exercise (decision of the project owner).
LESSON_HOURS = float(os.environ.get("LESSON_HOURS", "4"))


def _close(lesson: Lesson, when: float | None = None):
    lesson.closed, lesson.closed_at = True, when or lesson.clock()
    STORE.save_lesson(lesson)


def _expire_lessons():
    for lesson in list(LESSONS.values()):
        if not lesson.closed and not lesson.planned and lesson.clock() - lesson.started > LESSON_HOURS * 3600:
            _close(lesson, lesson.started + LESSON_HOURS * 3600)


def _new_code() -> str:
    """Join codes are unique among lessons that are open or planned (QA finding F-02)."""
    import secrets
    taken = {l.code for l in LESSONS.values() if not l.closed}
    while True:
        code = f"{secrets.randbelow(1_000_000):06d}"
        if code not in taken:
            return code


def _open_lesson(code: str) -> Lesson:
    _expire_lessons()
    lesson = next((l for l in LESSONS.values()
                   if l.code == code.strip() and not l.closed and not l.planned), None)
    if not lesson:
        raise HTTPException(404, "lesson code not found")
    return lesson


def _valid_members(lesson: Lesson, ids: list[str]) -> list[str]:
    allowed = {s["id"] for s in ROSTER.students(lesson.owner, lesson.class_name, active_only=True)}
    if any(i not in allowed for i in ids) or len(set(ids)) > 8:
        raise HTTPException(422, "unknown student")
    return list(dict.fromkeys(ids))


@app.get("/api/join/{code}")
def join_info(code: str, request: Request):
    """Names to tick on the join screen (anyone with the lesson code sees the class list)."""
    lesson = _code_lesson(code, request)
    taken = {m for sid in lesson.session_ids if sid in SESSIONS for m in SESSIONS[sid].members}
    return {"class_name": lesson.class_name,
            "roster": [{"id": s["id"], "name": s["name"], "taken": s["id"] in taken}
                       for s in ROSTER.students(lesson.owner, lesson.class_name, active_only=True)]}


# ---------- edge (live station) ----------
# Each edge agent authenticates with a device token. Set EDGE_TOKEN in production.
# One token per station (tools/add_station.py); the demo token works only with DEMO=1 (F-06).
STATION_TOKENS = StationTokens(STORE.root)
STATIONS: dict[str, LiveStation] = {}


def _device(token: str | None, station_id: str):
    if not STATION_TOKENS.valid(station_id, token):
        raise HTTPException(401, "device token required")


def _station(station_id: str) -> LiveStation:
    return STATIONS.setdefault(station_id, LiveStation(station_id))


@app.post("/api/edge/stations/{station_id}/obs")
def edge_obs(station_id: str, frames: list[dict] | dict, x_device_token: str | None = Header(None)):
    """One obs.v1 frame, or a list of them (an agent flushing its offline buffer)."""
    _device(x_device_token, station_id)
    st = _station(station_id)
    accepted = 0
    for f in frames if isinstance(frames, list) else [frames]:
        try:
            accepted += st.ingest(f)
        except FrameError as e:
            raise HTTPException(422, {"code": "BAD_FRAME", "detail": str(e), "seq": f.get("seq")})
    return {"accepted": accepted, "last_seq": st.last_seq}


@app.post("/api/edge/stations/{station_id}/status")
def edge_status(station_id: str, body: dict, x_device_token: str | None = Header(None)):
    _device(x_device_token, station_id)
    _station(station_id).heartbeat(body)
    return {"ok": True}


# ---------- teacher ----------
# Teacher login (lab/auth.py). With no accounts defined the teacher screens run in demo mode.
# TEACHER_TOKEN, when set, still lets scripts call the teacher API with an X-Teacher-Token header.
TEACHER_TOKEN = os.environ.get("TEACHER_TOKEN", "")
AUTH = Auth(STORE.root)


def require_teacher(request: Request) -> str:
    if TEACHER_TOKEN and request.headers.get("x-teacher-token") == TEACHER_TOKEN:
        return "script"
    if AUTH.demo:
        return DEMO_USER
    user = AUTH.user_from_cookie(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(401, "login required")
    return user


def _owns(user: str, lesson: Lesson) -> bool:
    return user in (DEMO_USER, "script") or lesson.owner in ("", user)


def _lesson(lid: str, user: str) -> Lesson:
    lesson = LESSONS.get(lid)
    if not lesson or not _owns(user, lesson):
        raise HTTPException(404, "lesson not found")    # another teacher's lesson looks like no lesson
    return lesson


def _teacher_session(sid: str, user: str) -> Session:
    s = _session(sid)
    lesson = LESSONS.get(s.lesson_id) if s.lesson_id else None
    if lesson and not _owns(user, lesson):
        raise HTTPException(404, "session not found")
    return s


class Login(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def login(body: Login, request: Request):
    ip = client_ip(request)
    if LOGIN_FAILS.blocked(ip):
        raise HTTPException(429, "locked")
    try:
        cookie = AUTH.login(body.username, body.password)
    except AuthError as e:
        LOGIN_FAILS.hit(ip)
        raise HTTPException(429 if str(e) == "locked" else 401, str(e))
    user = body.username.strip().lower()
    resp = JSONResponse({"user": user, "name": AUTH.name(user)})
    resp.set_cookie(COOKIE, cookie, max_age=12 * 3600, httponly=True, samesite="lax",
                    secure=cookie_secure(), path="/")
    return resp


@app.post("/api/auth/logout")
def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path="/")
    return resp


@app.get("/api/auth/me")
def me(request: Request):
    if AUTH.demo:
        return {"user": DEMO_USER, "name": "מצב הדגמה", "demo": True}
    user = AUTH.user_from_cookie(request.cookies.get(COOKIE))
    if not user:
        raise HTTPException(401, "login required")
    return {"user": user, "name": AUTH.name(user), "demo": False}


@app.post("/api/teacher/lessons")
def create_lesson(body: NewLesson, user: str = Depends(require_teacher)):
    if body.exercise_id not in content.exercises()["exercises"]:
        raise HTTPException(404, "exercise not found")
    if not 0 <= body.hint_quota <= 3 or body.deduction not in ("none", "per_hint") or not 1 <= body.stations <= 40:
        raise HTTPException(422, "invalid lesson settings")
    if not body.setup_ack:
        raise HTTPException(409, "setup and safety list not confirmed")
    lesson = Lesson(body.exercise_id, owner=user if user not in (DEMO_USER, "script") else "",
                    class_name=body.class_name.strip()[:40], date=body.date[:10], stations=body.stations,
                    hint_quota=body.hint_quota, allow_ask=body.allow_ask, deduction=body.deduction,
                    planned=body.planned)
    lesson.code = _new_code()
    LESSONS[lesson.id] = lesson
    STORE.save_lesson(lesson)
    return _live(lesson, SESSIONS)


@app.get("/api/teacher/exercises")
def teacher_exercises(user: str = Depends(require_teacher)):
    exs = content.exercises()["exercises"]
    return [{"id": k, "number": exercise_number(k), "title": v["title"], "subtitle": v["subtitle"],
             "status": v["status"], "available": resolve(RECORDINGS, v["recording"]) is not None}
            for k, v in exs.items()]


@app.get("/api/teacher/lessons")
def list_lessons(user: str = Depends(require_teacher)):
    _expire_lessons()
    return [{"id": l.id, "code": l.code, "exercise_id": l.exercise_id, "number": exercise_number(l.exercise_id),
             "title": content.exercises()["exercises"][l.exercise_id]["title"],
             "joined": len(l.session_ids), "stations": l.stations, "class_name": l.class_name, "date": l.date,
             "planned": l.planned, "closed": l.closed}
            for l in LESSONS.values() if _owns(user, l)]


def _roster_owner(user: str) -> str:
    return "" if user in (DEMO_USER, "script") else user


@app.get("/api/teacher/roster")
def roster_get(class_name: str, user: str = Depends(require_teacher)):
    return ROSTER.students(_roster_owner(user), class_name)


@app.post("/api/teacher/roster")
def roster_add(body: RosterAdd, user: str = Depends(require_teacher)):
    try:
        return ROSTER.add(_roster_owner(user), body.class_name.strip()[:40], body.names[:200])
    except RosterError as e:
        raise HTTPException(422, str(e))


@app.patch("/api/teacher/roster/{student_id}")
def roster_edit(student_id: str, body: RosterEdit, user: str = Depends(require_teacher)):
    try:
        return ROSTER.update(_roster_owner(user), body.class_name, student_id, body.name, body.active)
    except RosterError as e:
        raise HTTPException(404, str(e))


@app.post("/api/teacher/sessions/{sid}/members")
def set_members(sid: str, body: Members, user: str = Depends(require_teacher)):
    s = _teacher_session(sid, user)
    lesson = LESSONS.get(s.lesson_id) if s.lesson_id else None
    if not lesson:
        raise HTTPException(409, "not part of a lesson")
    with session_lock(sid):
        s.members = _valid_members(lesson, body.members)
        s._log("teacher.members", members=s.members)
        STORE.save_session(s)
    return {"members": s.members}


def _class_lessons(user: str) -> list[Lesson]:
    return [l for l in LESSONS.values() if _owns(user, l)]


@app.get("/api/teacher/students")
def students_overview(class_name: str, user: str = Depends(require_teacher)):
    return students.overview(_class_lessons(user), SESSIONS, class_name,
                             ROSTER.students(_roster_owner(user), class_name))


@app.get("/api/teacher/students/{student_id}")
def student_detail(student_id: str, class_name: str, user: str = Depends(require_teacher)):
    d = students.detail(_class_lessons(user), SESSIONS, class_name,
                        ROSTER.students(_roster_owner(user), class_name), student_id)
    if not d:
        raise HTTPException(404, "student not found")
    return d


class ContentEdit(BaseModel):
    changes: dict


def _who(user: str) -> str:
    return {"demo": "מצב הדגמה", "script": "סקריפט"}.get(user) or AUTH.name(user)


@app.get("/api/teacher/content")
def content_list(user: str = Depends(require_teacher)):
    exs = content.exercises()["exercises"]
    layer = content.overrides()
    return [{"id": k, "number": exercise_number(k), "title": v["title"], "subtitle": v["subtitle"],
             "status": v["status"], "errors": len(editor.validate(k)),
             "edited": k in layer.get("exercises", {}) or k in layer.get("answer_key", {})} for k, v in exs.items()]


@app.get("/api/teacher/content/export.yaml")
def content_export(user: str = Depends(require_teacher)):
    return Response(editor.export_yaml(), media_type="text/yaml; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="content-changes.yaml"'})


@app.get("/api/teacher/content/{eid}")
def content_get(eid: str, user: str = Depends(require_teacher)):
    try:
        return editor.current(eid)
    except editor.EditError as e:
        raise HTTPException(404, str(e))


@app.put("/api/teacher/content/{eid}")
def content_save(eid: str, body: ContentEdit, user: str = Depends(require_teacher)):
    try:
        res = editor.save(eid, body.changes, _who(user))
    except editor.EditError as e:
        raise HTTPException(422, str(e))
    return dict(res, exercise=editor.current(eid))


@app.post("/api/teacher/content/{eid}/{action}")
def content_action(eid: str, action: str, user: str = Depends(require_teacher)):
    try:
        if action == "approve":
            return editor.approve(eid, _who(user))
        if action == "revert":
            return editor.revert(eid, _who(user))
    except editor.EditError as e:
        raise HTTPException(409, str(e))
    raise HTTPException(404, "unknown action")


@app.get("/api/teacher/classes")
def classes(user: str = Depends(require_teacher)):
    out = classview.class_names([l for l in LESSONS.values() if _owns(user, l) and not l.planned])
    known = {c["name"] for c in out}
    # Classes that so far have only a roster (no lesson yet).
    return out + [{"name": c, "lessons": 0} for c in ROSTER.classes(_roster_owner(user)) if c not in known]


@app.get("/api/teacher/class")
def class_over_time(name: str, days: int | None = None, user: str = Depends(require_teacher)):
    if days is not None and not 1 <= days <= 3650:
        raise HTTPException(422, "days out of range")
    return classview.build([l for l in LESSONS.values() if _owns(user, l)], SESSIONS, name, days)


@app.get("/api/teacher/prep/stations")
def prep_stations(user: str = Depends(require_teacher)):
    """Stations a lesson can run on. MVP: the recorded station; live stations are listed for information."""
    out = [{"id": "ST-MOT-VFD-1", "name": "עמדה 1 · מנוע השראה עם ווסת תדר", "mode": "recording",
            "status": "הקלטות בלבד", "components": ["ווסת תדר", "מנוע השראה 370 W", "בלם מגנטי", "מד מומנט ומהירות", "מד רשת"],
            "usable": True}]
    for k, v in STATIONS.items():
        out.append({"id": k, "name": f"עמדה חיה {k}", "mode": "live", "status": "מחוברת" if v.connected else "מנותקת",
                    "components": [], "usable": False, "reason": "תרגול על נתונים חיים ייפתח אחרי אישור מפת הרגיסטרים של תלם"})
    return out


@app.get("/api/teacher/prep/{exercise_id}")
def prep_preview(exercise_id: str, user: str = Depends(require_teacher)):
    """One-page preview of what the students will see, plus the key (teacher only)."""
    data = content.exercises()
    ex = data["exercises"].get(exercise_id)
    if not ex:
        raise HTTPException(404, "exercise not found")
    key = content.answer_key()[exercise_id]
    rec = resolve(RECORDINGS, ex["recording"])
    cards = data["knowledge_cards"]
    chan = {c["key"]: c["name"] for g in content.channels()["groups"] for c in g["channels"]}
    return {
        "id": exercise_id, "number": exercise_number(exercise_id), "title": ex["title"], "subtitle": ex["subtitle"],
        "status": ex["status"],
        "student": {
            "goal": ex["goal"],
            "cards": [cards[c]["title"] for c in ex["cards"]],
            "check": ex["check"]["question"],
            "predict": ex["predict"]["prompt"],
            "observe": ex["observe_prompt"],
            "stop_s": ex["stop_s"],
            "hypotheses": [data["hypotheses"][h] for h in ex["hypothesis_options"]],
            "channels": [chan.get(c, c) for c in ex["initial_channels"] + ex["openable_channels"]],
            "hints": ex["hints"],
            "recheck": ex.get("recheck_prompt"),
            "exit": ex["exit_question"],
        },
        "key": {
            "check_answer": ex["check"]["choices"][key["check_answer"]],
            "cause": data["hypotheses"].get(key["cause"], key["cause"]),
            "evidence": [e["label"] for e in key["evidence"]],
            "conclusion": key["conclusion"],
        },
        "timeline": {
            "duration": len(rec.samples) if rec else 0, "stop_s": ex["stop_s"], "windows": ex.get("windows", {}),
            "runs": len(ex["recording"].split("+")),
        },
        "setup": dict(setup.teacher_setup(exercise_id, rec), mode="recording",
                      note="במצב הקלטה התלמידים לא מפעילים את העמדה: הנתונים מנוגנים מהקלטה. "
                           "ההגדרות כאן הן מצב ההתחלה שצריך לכוון בעמדה פיזית כדי לשחזר את התרגיל."),
    }


@app.get("/api/teacher/lessons/{lid}")
def lesson_live(lid: str, user: str = Depends(require_teacher)):
    _expire_lessons()
    return _live(_lesson(lid, user), SESSIONS)


@app.post("/api/teacher/lessons/{lid}/{action}")
def lesson_action(lid: str, action: str, user: str = Depends(require_teacher)):
    lesson = _lesson(lid, user)
    if action not in ("pause", "resume", "close", "open"):
        raise HTTPException(404, "unknown action")
    if action == "open":
        if lesson.planned:
            lesson.planned, lesson.started = False, lesson.clock()
            STORE.save_lesson(lesson)
        return _live(lesson, SESSIONS)
    for sid in lesson.session_ids:
        if sid not in SESSIONS:
            continue
        with session_lock(sid):
            if action == "pause":
                SESSIONS[sid].pause()
            elif action == "resume":
                SESSIONS[sid].resume()
            STORE.save_session(SESSIONS[sid])
    if action == "close" and not lesson.closed:
        _close(lesson)
    return _live(lesson, SESSIONS)


@app.get("/api/teacher/stations")
def stations(user: str = Depends(require_teacher)):
    return [{"station": k, "connected": v.connected, "samples": len(v.samples)} for k, v in STATIONS.items()]


@app.get("/api/teacher/stations/{station_id}/monitor")
def station_monitor(station_id: str, user: str = Depends(require_teacher)):
    if station_id not in STATIONS:
        raise HTTPException(404, "station has not connected yet")
    return STATIONS[station_id].monitor()


@app.get("/api/teacher/lessons/{lid}/export.csv")
def export(lid: str, user: str = Depends(require_teacher)):
    lesson = _lesson(lid, user)
    return Response(teacher.export_csv(lesson, SESSIONS), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="lesson-{lesson.code}-grades.csv"'})


@app.post("/api/teacher/sessions/{sid}/scores")
def confirm(sid: str, body: Scores, user: str = Depends(require_teacher)):
    s = _teacher_session(sid, user)
    with session_lock(sid):
        try:
            teacher.confirm_scores(s, body.scores, body.note)
        except ValueError as e:
            raise HTTPException(422, str(e))
        STORE.save_session(s)
    return _detail(s)


@app.get("/api/teacher/sessions/{sid}")
def session_detail(sid: str, user: str = Depends(require_teacher)):
    return _detail(_teacher_session(sid, user))


@app.post("/api/teacher/sessions/{sid}/{action}")
def session_action(sid: str, action: str, body: Text | None = None, user: str = Depends(require_teacher)):
    s = _teacher_session(sid, user)
    if action not in ("pause", "resume", "hint", "message", "release"):
        raise HTTPException(404, "unknown action")
    if action == "release":                     # the group moves to another tablet: next device claims it
        with session_lock(sid):
            s.token = ""
            s._log("teacher.released_device")
            STORE.save_session(s)
        return _detail(s)
    with session_lock(sid):
        try:
            if action == "pause":
                s.pause()
            elif action == "resume":
                s.resume()
            elif action == "hint":
                s.teacher_hint()
            else:
                s.send_message(body.text if body else "")
        except GuardError as e:
            raise HTTPException(409, {"code": "STATE_GUARD_FAILED", "detail": str(e)})
        STORE.save_session(s)
    return _detail(s)


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return _session(sid).student_view()


@app.post("/api/sessions/{sid}/advance")
def advance(sid: str):
    return _run(sid, lambda s: s.advance())


@app.post("/api/sessions/{sid}/theory")
def theory(sid: str, body: Choice):
    return _run(sid, lambda s: s.answer_theory(body.choice))


@app.post("/api/sessions/{sid}/prediction")
def prediction(sid: str, body: Prediction):
    return _run(sid, lambda s: s.submit_prediction(body.directions, body.text))


@app.post("/api/sessions/{sid}/hypothesis")
def hypothesis(sid: str, body: Code):
    return _run(sid, lambda s: s.choose_hypothesis(body.code))


@app.post("/api/sessions/{sid}/channels/{key}/open")
def open_channel(sid: str, key: str, body: OpenChannel):
    return _run(sid, lambda s: s.open_channel(key, body.expectation))


@app.post("/api/sessions/{sid}/channels/{key}/close")
def close_channel(sid: str, key: str):
    return _run(sid, lambda s: s.close_channel(key))


@app.post("/api/sessions/{sid}/readings")
def add_reading(sid: str, body: ReadingIn):
    return _run(sid, lambda s: s.add_reading(body.channel, body.t))


@app.delete("/api/sessions/{sid}/readings/{rid}")
def remove_reading(sid: str, rid: str):
    return _run(sid, lambda s: s.remove_reading(rid))


@app.post("/api/sessions/{sid}/hints")
def hint(sid: str):
    return _run(sid, lambda s: s.request_hint())


@app.post("/api/sessions/{sid}/ask")
def ask(sid: str, body: Text):
    return _run(sid, lambda s: s.ask(body.text))


@app.get("/api/status")
def status():
    return {"llm": TUTOR.live, "llm_configured": llm.enabled(), "model_phrase": llm.MODEL_PHRASE,
            "model_classify": llm.MODEL_CLASSIFY, "recordings": sorted(RECORDINGS),
            "demo": AUTH.demo, "teacher_accounts": AUTH.has_accounts}


@app.post("/api/sessions/{sid}/reason")
def reason(sid: str, body: Reason):
    return _run(sid, lambda s: s.submit_reason(body.text, body.cited))


@app.post("/api/sessions/{sid}/exit")
def exit_answer(sid: str, body: Text):
    return _run(sid, lambda s: s.submit_exit(body.text))


# Built front end (apps/web/dist). Any non-API path serves the single-page app.
DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        return FileResponse(DIST / "index.html")
