"""Keep sessions and lessons on disk so a server restart does not lose a lesson in progress.

One JSON file per session / lesson under var/state/, rewritten atomically after every change.
Times are wall-clock seconds, so they stay valid across restarts.
"""
from __future__ import annotations

import itertools
import json
import os
import time
from dataclasses import fields
from pathlib import Path

from .ingest import resolve
from .session import Session
from .teacher import Lesson

SKIP = {"recording", "clock", "log_path", "tutor", "_ids"}


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class Store:
    def __init__(self, root: Path):
        self.root = root

    def save_session(self, s: Session):
        n = next(s._ids)
        s._ids = itertools.count(n)          # peek without consuming
        data = {f.name: getattr(s, f.name) for f in fields(s) if f.name not in SKIP}
        data.update(recording_name=s.recording.run_id, alias=s.alias, next_id=n)
        _write(self.root / "sessions" / f"{s.id}.json", data)

    def save_lesson(self, lesson: Lesson):
        data = {f.name: getattr(lesson, f.name) for f in fields(lesson) if f.name != "clock"}
        _write(self.root / "lessons" / f"{lesson.id}.json", data)

    def load(self, recordings: dict, *, log_path: Path | None, replay_speed: float, tutor) -> tuple[dict, dict]:
        sessions, lessons = {}, {}
        for p in sorted((self.root / "sessions").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            rec = resolve(recordings, d.pop("recording_name"))
            if rec is None:
                continue
            s = Session(d["exercise_id"], rec, clock=time.time, log_path=None, replay_speed=replay_speed, tutor=tutor)
            s._ids = itertools.count(d.pop("next_id"))
            for k, v in d.items():
                setattr(s, k, v)
            s.log_path = log_path
            sessions[s.id] = s
        for p in sorted((self.root / "lessons").glob("*.json")):
            d = json.loads(p.read_text(encoding="utf-8"))
            lesson = Lesson(d["exercise_id"], clock=time.time)
            for k, v in d.items():
                setattr(lesson, k, v)
            lessons[lesson.id] = lesson
        return sessions, lessons
