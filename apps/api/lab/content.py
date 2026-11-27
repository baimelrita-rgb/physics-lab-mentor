"""Load content files. Student-facing content and the answer key are kept apart."""
from __future__ import annotations

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


@lru_cache
def exercises() -> dict:
    return _load("exercises.yaml")


@lru_cache
def answer_key() -> dict:
    """Server only. Only diagnosis.py and the teacher API may call this."""
    return _load("answer_key.yaml")
