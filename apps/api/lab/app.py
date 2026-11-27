"""HTTP API (technical design §7, the student part). Run: uvicorn lab.app:app"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import content
from .ingest import load_all
from .session import GuardError, Session

app = FastAPI(title="Lab Mentor")
RECORDINGS = load_all(content.DATA)
SESSIONS: dict[str, Session] = {}
LOG = content.ROOT / "var" / "learning_log.jsonl"
SPEED = float(os.environ.get("REPLAY_SPEED", "1"))


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
    return s.student_view()


class NewSession(BaseModel):
    exercise_id: str


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
    exs = content.exercises()["exercises"]
    return [{"id": k, "title": v["title"], "subtitle": v["subtitle"], "status": v["status"],
             "available": v["recording"] in RECORDINGS} for k, v in exs.items()]


@app.post("/api/sessions")
def create_session(body: NewSession):
    ex = content.exercises()["exercises"].get(body.exercise_id)
    if not ex or ex["recording"] not in RECORDINGS:
        raise HTTPException(404, "exercise or recording not available")
    s = Session(body.exercise_id, RECORDINGS[ex["recording"]], log_path=LOG, replay_speed=SPEED)
    SESSIONS[s.id] = s
    return s.student_view()


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
