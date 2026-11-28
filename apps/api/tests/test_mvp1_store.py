"""MVP package 1 + 6: SQLite store, per-session locks, migration from JSON files, backup."""
import concurrent.futures as cf
import json
import sqlite3

from fastapi import HTTPException

from lab import app as appmod, content
from lab.ingest import load_all, resolve
from lab.session import Session
from lab.store import Store


def _session():
    rec = resolve(load_all(content.DATA), "E03")
    return Session("EX-01", rec)


def test_parallel_actions_on_one_session_never_fail():
    s = _session()
    appmod.SESSIONS[s.id] = s
    s.answer_theory(0); s.advance(); s.submit_prediction({"speed_rpm": "down"})
    results = []

    def act(_):
        try:
            appmod._run(s.id, lambda x: x.advance())
            return 200
        except HTTPException as e:
            return e.status_code

    with cf.ThreadPoolExecutor(16) as ex:
        results = list(ex.map(act, range(50)))
    assert results.count(200) == 1 and set(results) <= {200, 409}      # exactly one step forward, no 500
    assert s.state == "OBSERVE"
    row = appmod.STORE.db.execute("SELECT data FROM sessions WHERE id = ?", (s.id,)).fetchone()
    assert json.loads(row[0])["state"] == "OBSERVE"


def test_ids_are_128_bit():
    assert len(_session().id) == 32


def test_json_folders_are_imported_once(tmp_path):
    s = _session()
    doc = Store.session_doc(s)
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / f"{s.id}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    store = Store(tmp_path)
    sessions, _ = store.load(load_all(content.DATA), log_path=None, replay_speed=1, tutor=None)
    assert s.id in sessions and (tmp_path / "sessions.migrated").is_dir()
    assert s.id in Store(tmp_path).load(load_all(content.DATA), log_path=None, replay_speed=1, tutor=None)[0]


def test_online_backup(tmp_path):
    store = Store(tmp_path / "a")
    store.save_session(_session())
    store.backup(tmp_path / "b" / "copy.db")
    assert sqlite3.connect(tmp_path / "b" / "copy.db").execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
