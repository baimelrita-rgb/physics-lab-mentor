"""Station setup per exercise: starting settings of each component (content/setup.yaml)
plus, for the teacher, the run scenario and an envelope check of the recording."""
from __future__ import annotations

from functools import lru_cache

import yaml

from . import content, envelope

ALWAYS = {"GRID", "VFD-01", "MOT-01", "LOAD-01", "CTL-01"}   # the motor has to run in every exercise


@lru_cache
def data() -> dict:
    return yaml.safe_load((content.CONTENT / "setup.yaml").read_text(encoding="utf-8"))


def used_channels(ex: dict) -> set[str]:
    return set(ex["initial_channels"]) | set(ex["openable_channels"]) | set(ex["predict"]["channels"])


def start_setup(exercise_id: str) -> dict:
    """Student-safe: the starting state only, nothing about what will change."""
    d = data()
    ex = content.exercises()["exercises"][exercise_id]
    point = d["operating_points"][d["exercises"][exercise_id]["start"]]
    used = used_channels(ex)
    idx = content.channel_index()
    comps = []
    for cid in d["path"] + ["CTL-01"]:
        c = d["components"][cid]
        settings = list(point["settings"].get(cid, [])) + list(d["common"].get(cid, []))
        comps.append({
            "id": cid, "name": c["name"], "model": c["model"],
            "needed": cid in ALWAYS or bool(used & set(c["channels"])),
            "channels": [idx[k]["name"] for k in c["channels"] if k in used and k in idx],
            "settings": settings,
        })
    expect = [{"channel": k, "name": idx[k]["name"], "unit": idx[k]["unit"], "value": v}
              for k, v in point["expect"].items() if k in idx]
    return {"point": point["label"], "components": comps, "expect": expect}


def teacher_setup(exercise_id: str, recording) -> dict:
    out = start_setup(exercise_id)
    key = content.answer_key()[exercise_id]
    names = {c["id"]: c["name"] for c in out["components"]}
    out["scenario"] = [dict(s, component_name=names.get(s["component"], s["component"])) for s in key.get("scenario", [])]
    out["live"] = key.get("live", {"ok": True, "note": ""})
    worst: dict[str, dict] = {}
    for e in envelope.for_recording(recording) if recording else []:
        if e["rule"] not in worst or (e["level"] == "stop" and worst[e["rule"]]["level"] != "stop"):
            worst[e["rule"]] = e
    out["envelope"] = [{"id": r["id"], "title": r["title"], "status": r["status"],
                        "level": worst[r["id"]]["level"] if r["id"] in worst else "ok",
                        "value": worst[r["id"]]["value"] if r["id"] in worst else None,
                        "limit": worst[r["id"]]["limit"] if r["id"] in worst else None}
                       for r in envelope.rules()]
    return out
