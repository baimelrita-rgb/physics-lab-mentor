"""HTTP API (technical design §7, the student part). Run: uvicorn lab.app:app"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import content, llm, teacher
from .ingest import load_all, resolve
from .live import FrameError, LiveStation
from .session import GuardError, Session, exercise_number
from .teacher import Lesson
from .store import Store
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


def _run(sid: str, fn):
    s = _session(sid)
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


class NewLesson(BaseModel):
    exercise_id: str


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


def _new_session(exercise_id: str, label: str, lesson: Lesson | None = None) -> Session:
    ex = content.exercises()["exercises"].get(exercise_id)
    rec = resolve(RECORDINGS, ex["recording"]) if ex else None
    if not rec:
        raise HTTPException(404, "exercise or recording not available")
    s = Session(exercise_id, rec, log_path=LOG, replay_speed=SPEED,
                label=label.strip()[:30] or "עמדה", lesson_id=lesson.id if lesson else None, tutor=TUTOR)
    SESSIONS[s.id] = s
    STORE.save_session(s)
    if lesson:
        lesson.session_ids.append(s.id)
        STORE.save_lesson(lesson)
    return s


@app.post("/api/sessions")
def create_session(body: NewSession):
    return _new_session(body.exercise_id, body.label).student_view()


@app.post("/api/join")
def join(body: Join):
    lesson = next((l for l in LESSONS.values() if l.code == body.code.strip() and not l.closed), None)
    if not lesson:
        raise HTTPException(404, "lesson code not found")
    return _new_session(lesson.exercise_id, body.label, lesson).student_view()


# ---------- edge (live station) ----------
# Each edge agent authenticates with a device token. Set EDGE_TOKEN in production.
EDGE_TOKEN = os.environ.get("EDGE_TOKEN", "dev-edge-token")
STATIONS: dict[str, LiveStation] = {}


def _device(token: str | None):
    if token != EDGE_TOKEN:
        raise HTTPException(401, "device token required")


def _station(station_id: str) -> LiveStation:
    return STATIONS.setdefault(station_id, LiveStation(station_id))


@app.post("/api/edge/stations/{station_id}/obs")
def edge_obs(station_id: str, frames: list[dict] | dict, x_device_token: str | None = Header(None)):
    """One obs.v1 frame, or a list of them (an agent flushing its offline buffer)."""
    _device(x_device_token)
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
    _device(x_device_token)
    _station(station_id).heartbeat(body)
    return {"ok": True}


# ---------- teacher ----------
# Demo protection only: set TEACHER_TOKEN to require it. Real teacher login (OIDC) comes before a pilot.
TEACHER_TOKEN = os.environ.get("TEACHER_TOKEN", "")


def _teacher(token: str | None):
    if TEACHER_TOKEN and token != TEACHER_TOKEN:
        raise HTTPException(401, "teacher token required")


def _lesson(lid: str) -> Lesson:
    if lid not in LESSONS:
        raise HTTPException(404, "lesson not found")
    return LESSONS[lid]


@app.post("/api/teacher/lessons")
def create_lesson(body: NewLesson, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    if body.exercise_id not in content.exercises()["exercises"]:
        raise HTTPException(404, "exercise not found")
    lesson = Lesson(body.exercise_id)
    LESSONS[lesson.id] = lesson
    STORE.save_lesson(lesson)
    return teacher.live(lesson, SESSIONS)


@app.get("/api/teacher/exercises")
def teacher_exercises(x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    exs = content.exercises()["exercises"]
    return [{"id": k, "number": exercise_number(k), "title": v["title"], "subtitle": v["subtitle"],
             "status": v["status"], "available": resolve(RECORDINGS, v["recording"]) is not None}
            for k, v in exs.items()]


@app.get("/api/teacher/lessons")
def list_lessons(x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    return [{"id": l.id, "code": l.code, "exercise_id": l.exercise_id, "stations": len(l.session_ids),
             "closed": l.closed} for l in LESSONS.values()]


@app.get("/api/teacher/lessons/{lid}")
def lesson_live(lid: str, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    return teacher.live(_lesson(lid), SESSIONS)


@app.post("/api/teacher/lessons/{lid}/{action}")
def lesson_action(lid: str, action: str, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    lesson = _lesson(lid)
    for sid in lesson.session_ids:
        if action == "pause":
            SESSIONS[sid].pause()
        elif action == "resume":
            SESSIONS[sid].resume()
        elif action != "close":
            raise HTTPException(404, "unknown action")
        STORE.save_session(SESSIONS[sid])
    if action == "close":
        lesson.closed = True
        STORE.save_lesson(lesson)
    return teacher.live(lesson, SESSIONS)


@app.get("/api/teacher/stations")
def stations(x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    return [{"station": k, "connected": v.connected, "samples": len(v.samples)} for k, v in STATIONS.items()]


@app.get("/api/teacher/stations/{station_id}/monitor")
def station_monitor(station_id: str, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    if station_id not in STATIONS:
        raise HTTPException(404, "station has not connected yet")
    return STATIONS[station_id].monitor()


@app.get("/api/teacher/lessons/{lid}/export.csv")
def export(lid: str, x_teacher_token: str | None = Header(None), token: str | None = None):
    _teacher(x_teacher_token or token)
    lesson = _lesson(lid)
    return Response(teacher.export_csv(lesson, SESSIONS), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="lesson-{lesson.code}-grades.csv"'})


@app.post("/api/teacher/sessions/{sid}/scores")
def confirm(sid: str, body: Scores, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    s = _session(sid)
    try:
        teacher.confirm_scores(s, body.scores, body.note)
    except ValueError as e:
        raise HTTPException(422, str(e))
    STORE.save_session(s)
    return teacher.detail(s)


@app.get("/api/teacher/sessions/{sid}")
def session_detail(sid: str, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    return teacher.detail(_session(sid))


@app.post("/api/teacher/sessions/{sid}/{action}")
def session_action(sid: str, action: str, body: Text | None = None, x_teacher_token: str | None = Header(None)):
    _teacher(x_teacher_token)
    s = _session(sid)
    try:
        if action == "pause":
            s.pause()
        elif action == "resume":
            s.resume()
        elif action == "hint":
            s.teacher_hint()
        elif action == "message":
            s.send_message(body.text if body else "")
        else:
            raise HTTPException(404, "unknown action")
    except GuardError as e:
        raise HTTPException(409, {"code": "STATE_GUARD_FAILED", "detail": str(e)})
    STORE.save_session(s)
    return teacher.detail(s)


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
            "model_classify": llm.MODEL_CLASSIFY, "recordings": sorted(RECORDINGS)}


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
