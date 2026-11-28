"""Load content files. Student-facing content and the answer key are kept apart."""
from __future__ import annotations

import contextlib
import contextvars
import copy
import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONTENT = ROOT / "content"
DATA = ROOT / "data"


def _load(name: str) -> dict:
    return yaml.safe_load((CONTENT / name).read_text(encoding="utf-8"))


@lru_cache
def channels() -> dict:
    return _load("channels.yaml")


@lru_cache
def channel_index() -> dict[str, dict]:
    out = {}
    for g in channels()["groups"]:
        for c in g["channels"]:
            out[c["key"]] = {**c, "group": g["id"], "group_title": g["title"]}
    return out


# Edits made in the teacher's "content" tab are a layer over the repository files (lab/editor.py).
# Each tenant (school / network) has its own layer, so one school's edits never reach another
# (MVP package 4). The request's tenant is set once by the server (app.guard) in a context variable.
DEFAULT_TENANT = "default"
_TENANT: contextvars.ContextVar[str] = contextvars.ContextVar("tenant", default=DEFAULT_TENANT)
_TENANT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


def valid_tenant(t: str) -> bool:
    return bool(_TENANT_ID.match(t or ""))


def current_tenant() -> str:
    return _TENANT.get()


def set_tenant(t: str):
    if not valid_tenant(t):
        raise ValueError("bad tenant id")
    return _TENANT.set(t)


@contextlib.contextmanager
def use_tenant(t: str):
    token = set_tenant(t)
    try:
        yield
    finally:
        _TENANT.reset(token)


def overrides_file(tenant: str | None = None) -> Path:
    tenant = tenant or current_tenant()
    name = "content_overrides.json" if tenant == DEFAULT_TENANT else f"content_overrides.{tenant}.json"
    return Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")) / name


def overrides() -> dict:
    f = overrides_file()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def set_path(d: dict, path: str, value):
    *parents, last = path.split(".")
    for p in parents:
        d = d.setdefault(p, {})
    d[last] = value


def get_path(d: dict, path: str):
    for p in path.split("."):
        d = d[p]
    return d


def _apply(base: dict, layer: dict) -> dict:
    out = copy.deepcopy(base)
    for eid, fields in layer.items():
        if eid in out:
            for path, value in fields.items():
                set_path(out[eid], path, value)
    return out


@lru_cache
def base_exercises() -> dict:
    return _load("exercises.yaml")


@lru_cache
def base_answer_key() -> dict:
    return _load("answer_key.yaml")


_CACHE: dict[tuple[str, str], dict] = {}
_CACHE_LOCK = threading.Lock()


def _cached(kind: str, build) -> dict:
    k = (kind, current_tenant())
    with _CACHE_LOCK:
        if k not in _CACHE:
            _CACHE[k] = build()
        return _CACHE[k]


def exercises() -> dict:
    """Exercises of the current tenant (repository files + that tenant's edits)."""
    def build():
        data = copy.deepcopy(base_exercises())
        data["exercises"] = _apply(data["exercises"], overrides().get("exercises", {}))
        return data
    return _cached("exercises", build)


def answer_key() -> dict:
    """Server only. Only diagnosis.py and the teacher API may call this."""
    return _cached("key", lambda: _apply(base_answer_key(), overrides().get("answer_key", {})))


def snapshot(exercise_id: str) -> dict:
    """Frozen copy of everything a session needs about its exercise, with a short version id.
    A session keeps this copy, so editing the exercise later never changes a running or
    graded session (MVP package 5)."""
    import hashlib
    doc = {"exercise": copy.deepcopy(exercises()["exercises"][exercise_id]),
           "key": copy.deepcopy(answer_key()[exercise_id]),
           "redirects": copy.deepcopy(answer_key().get("misconception_redirects", {}))}
    raw = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    doc["version"] = hashlib.sha256(raw).hexdigest()[:12]
    doc["tenant"] = current_tenant()
    return doc


def reload():
    with _CACHE_LOCK:
        _CACHE.clear()
