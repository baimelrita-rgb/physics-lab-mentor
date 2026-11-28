"""Load content files. Student-facing content and the answer key are kept apart."""
from __future__ import annotations

import copy
import json
import os
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
def overrides_file() -> Path:
    return Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")) / "content_overrides.json"


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


@lru_cache
def exercises() -> dict:
    data = copy.deepcopy(base_exercises())
    data["exercises"] = _apply(data["exercises"], overrides().get("exercises", {}))
    return data


@lru_cache
def answer_key() -> dict:
    """Server only. Only diagnosis.py and the teacher API may call this."""
    return _apply(base_answer_key(), overrides().get("answer_key", {}))


def reload():
    exercises.cache_clear()
    answer_key.cache_clear()
