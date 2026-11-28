"""Persistent state in SQLite (one file: <STATE_DIR>/lab.db, WAL mode).

Sessions and lessons are stored as JSON documents in rows, with the columns the server
filters on (tenant, lesson, code, owner) kept as real columns. Every write is a single
transaction, so a crash never leaves a half-written record, and parallel requests on the
same session cannot corrupt it (the app also takes a lock per session).

The first start after an upgrade imports the old one-JSON-file-per-record folders
(sessions/, lessons/) and renames them to *.migrated.
Times are wall-clock seconds, so they stay valid across restarts.
"""
from __future__ import annotations

import itertools
import json
import sqlite3
import threading
import time
from dataclasses import fields
from pathlib import Path

from .ingest import resolve
from .session import Session
from .teacher import Lesson

SKIP = {"recording", "clock", "log_path", "tutor", "_ids"}
DEFAULT_TENANT = "default"
SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lessons (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    owner TEXT NOT NULL DEFAULT '',
    code TEXT NOT NULL,
    closed INTEGER NOT NULL DEFAULT 0,
    data TEXT NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS lessons_tenant ON lessons (tenant_id, owner);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    lesson_id TEXT,
    data TEXT NOT NULL,
    updated REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_lesson ON sessions (lesson_id);
"""


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "lab.db"
        self._lock = threading.Lock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        self._import_json_folders()

    # ---------- writes ----------
    @staticmethod
    def session_doc(s: Session) -> dict:
        n = next(s._ids)
        s._ids = itertools.count(n)          # peek without consuming
        data = {f.name: getattr(s, f.name) for f in fields(s) if f.name not in SKIP}
        data.update(recording_name=s.recording.run_id, alias=s.alias, next_id=n)
        return data

    def save_session(self, s: Session, tenant_id: str = DEFAULT_TENANT):
        doc = json.dumps(self.session_doc(s), ensure_ascii=False)
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO sessions (id, tenant_id, lesson_id, data, updated) VALUES (?, ?, ?, ?, ?)",
                            (s.id, getattr(s, "tenant_id", tenant_id) or tenant_id, s.lesson_id, doc, time.time()))

    def save_lesson(self, lesson: Lesson):
        data = {f.name: getattr(lesson, f.name) for f in fields(lesson) if f.name != "clock"}
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO lessons (id, tenant_id, owner, code, closed, data, updated) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (lesson.id, getattr(lesson, "tenant_id", DEFAULT_TENANT), lesson.owner, lesson.code,
                             int(lesson.closed), json.dumps(data, ensure_ascii=False), time.time()))

    # ---------- reads ----------
    def load(self, recordings: dict, *, log_path: Path | None, replay_speed: float, tutor) -> tuple[dict, dict]:
        sessions, lessons = {}, {}
        for (raw,) in self.db.execute("SELECT data FROM sessions ORDER BY updated"):
            d = json.loads(raw)
            rec = resolve(recordings, d.pop("recording_name"))
            if rec is None:
                continue
            s = Session(d["exercise_id"], rec, clock=time.time, log_path=None, replay_speed=replay_speed, tutor=tutor)
            s._ids = itertools.count(d.pop("next_id"))
            for k, v in d.items():
                setattr(s, k, v)
            s.log_path = log_path
            sessions[s.id] = s
        for (raw,) in self.db.execute("SELECT data FROM lessons ORDER BY updated"):
            d = json.loads(raw)
            lesson = Lesson(d["exercise_id"], clock=time.time)
            for k, v in d.items():
                setattr(lesson, k, v)
            lessons[lesson.id] = lesson
        return sessions, lessons

    # ---------- maintenance ----------
    def backup(self, target: Path):
        """Consistent copy of the database while the server runs (SQLite online backup)."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        dst = sqlite3.connect(target)
        with self._lock:
            self.db.backup(dst)
        dst.close()

    def _import_json_folders(self):
        """One-time import of the old JSON-file store."""
        for kind in ("sessions", "lessons"):
            folder = self.root / kind
            if not folder.is_dir():
                continue
            files = sorted(folder.glob("*.json"))
            with self._lock:
                for p in files:
                    d = json.loads(p.read_text(encoding="utf-8"))
                    if kind == "sessions":
                        self.db.execute("INSERT OR IGNORE INTO sessions (id, tenant_id, lesson_id, data, updated) "
                                        "VALUES (?, ?, ?, ?, ?)",
                                        (d["id"], DEFAULT_TENANT, d.get("lesson_id"), json.dumps(d, ensure_ascii=False),
                                         p.stat().st_mtime))
                    else:
                        self.db.execute("INSERT OR IGNORE INTO lessons (id, tenant_id, owner, code, closed, data, updated) "
                                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                        (d["id"], DEFAULT_TENANT, d.get("owner", ""), d["code"], int(d.get("closed", False)),
                                         json.dumps(d, ensure_ascii=False), p.stat().st_mtime))
            folder.rename(folder.with_name(kind + ".migrated"))
