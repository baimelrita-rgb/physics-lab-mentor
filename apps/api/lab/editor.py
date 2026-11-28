"""Teacher content editing (UI doc · teacher screens · "content").

Edits are stored as a layer over the repository files (content_overrides.json in the state folder),
with a history of every change. The repository YAML stays the reviewed source of truth: the
teacher can revert an exercise to it, or export the changes to update the repository.

Rules enforced on every save:
- student-facing texts must not contain any of the exercise's leak terms (the answer wall);
- hints are questions (end with "?"), exactly three, short;
- the theory check has 2-4 choices and the right answer is one of them;
- any change returns the exercise to "draft" until a teacher approves it again.
"""
from __future__ import annotations

import copy
import json
import os
import time

import yaml

from . import content

# path -> (label, kind, audience)
EX_FIELDS = {
    "title": ("שם התרגיל", "text", "teacher"),
    "subtitle": ("כותרת משנה", "text", "teacher"),
    "goal": ("מטרה", "text", "student"),
    "check.question": ("שאלת הבנה", "text", "student"),
    "check.choices": ("תשובות לבחירה", "list", "student"),
    "predict.prompt": ("שאלת תחזית", "text", "student"),
    "observe_prompt": ("הנחיה לצפייה", "text", "student"),
    "hints": ("רמזים", "list", "student"),
    "recheck_prompt": ("בדיקה חוזרת", "text", "student"),
    "exit_question": ("שאלת יציאה", "text", "student"),
}
KEY_FIELDS = {
    "check_answer": ("התשובה הנכונה", "index", "teacher"),
    "conclusion": ("מסקנה מצופה", "text", "teacher"),
    "leak_terms": ("מילים שאסור למנטור ולתלמיד לראות", "list", "teacher"),
}
MAX_TEXT, MAX_HINT = 400, 220


class EditError(Exception):
    pass


def _save(data: dict):
    f = content.overrides_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
    content.reload()


def _get(d: dict, path: str):
    try:
        return content.get_path(d, path)
    except (KeyError, TypeError):
        return None


def current(eid: str) -> dict:
    ex = content.exercises()["exercises"].get(eid)
    if ex is None:
        raise EditError("exercise not found")
    key = content.answer_key()[eid]
    base_ex = content.base_exercises()["exercises"][eid]
    base_key = content.base_answer_key()[eid]
    layer = content.overrides()
    meta = layer.get("meta", {}).get(eid, {})
    fields = []
    for path, (label, kind, aud) in EX_FIELDS.items():
        if path == "recheck_prompt" and "recheck_prompt" not in base_ex:
            continue
        fields.append({"path": path, "label": label, "kind": kind, "audience": aud, "source": "exercise",
                       "value": _get(ex, path), "changed": _get(ex, path) != _get(base_ex, path)})
    for path, (label, kind, aud) in KEY_FIELDS.items():
        fields.append({"path": path, "label": label, "kind": kind, "audience": aud, "source": "key",
                       "value": key.get(path), "changed": key.get(path) != base_key.get(path)})
    return {
        "id": eid, "number": int(eid.split("-")[-1]), "status": ex["status"], "base_status": base_ex["status"],
        "approved_by": meta.get("approved_by"), "approved_at": meta.get("approved_at"),
        "fields": fields, "errors": validate(eid),
        "fixed": {"recording": ex["recording"], "stop_s": ex["stop_s"], "windows": ex.get("windows"),
                  "cause": content.exercises()["hypotheses"].get(key["cause"], key["cause"]),
                  "evidence": [e["label"] for e in key["evidence"]]},
        "history": [h for h in layer.get("history", []) if h["exercise"] == eid][-30:][::-1],
    }


def validate(eid: str, ex: dict | None = None, key: dict | None = None) -> list[dict]:
    ex = ex if ex is not None else content.exercises()["exercises"][eid]
    key = key if key is not None else content.answer_key()[eid]
    errs = []

    def err(path, msg):
        errs.append({"path": path, "message": msg})

    terms = [t for t in (key.get("leak_terms") or []) if t.strip()]
    if not terms:
        err("leak_terms", "צריך לפחות מילה אחת שחושפת את התשובה, כדי שהמנטור יידע ממה להימנע.")
    for path, (label, kind, aud) in EX_FIELDS.items():
        v = _get(ex, path)
        if v is None and path == "recheck_prompt":
            continue
        values = v if isinstance(v, list) else [v]
        if not values or any(not (x or "").strip() for x in values):
            err(path, "שדה ריק.")
            continue
        for x in values:
            if len(x) > MAX_TEXT:
                err(path, f"ארוך מדי ({len(x)} תווים, עד {MAX_TEXT}).")
        if aud == "student":
            for x in values:
                hit = [t for t in terms if t in x]
                if hit:
                    err(path, f"חושף את התשובה: ״{hit[0]}״.")
    hints = ex.get("hints") or []
    if len(hints) != 3:
        err("hints", "צריך בדיוק שלושה רמזים.")
    for i, h in enumerate(hints):
        if h and not h.strip().endswith("?"):
            err("hints", f"רמז {i + 1} צריך להיות שאלה (להסתיים בסימן שאלה).")
        if h and len(h) > MAX_HINT:
            err("hints", f"רמז {i + 1} ארוך מדי ({len(h)} תווים, עד {MAX_HINT}).")
    choices = _get(ex, "check.choices") or []
    if not 2 <= len(choices) <= 4:
        err("check.choices", "צריך 2 עד 4 תשובות.")
    if len(set(choices)) != len(choices):
        err("check.choices", "יש תשובה כפולה.")
    if not isinstance(key.get("check_answer"), int) or not 0 <= key["check_answer"] < len(choices):
        err("check_answer", "התשובה הנכונה צריכה להיות אחת מהתשובות.")
    return errs


def save(eid: str, changes: dict, user: str) -> dict:
    """changes: {path: value} for EX_FIELDS and KEY_FIELDS paths."""
    if eid not in content.exercises()["exercises"]:
        raise EditError("exercise not found")
    unknown = set(changes) - set(EX_FIELDS) - set(KEY_FIELDS)
    if unknown:
        raise EditError(f"field not editable: {sorted(unknown)[0]}")
    ex = copy.deepcopy(content.exercises()["exercises"][eid])
    key = copy.deepcopy(content.answer_key()[eid])
    clean = {}
    for path, value in changes.items():
        kind = (EX_FIELDS.get(path) or KEY_FIELDS[path])[1]
        if kind == "text":
            value = " ".join(str(value).split())
        elif kind == "list":
            if not isinstance(value, list):
                raise EditError(f"{path} must be a list")
            value = [" ".join(str(x).split()) for x in value]
            if path == "leak_terms":
                value = [x for x in value if x]
        elif kind == "index":
            value = int(value)
        clean[path] = value
        content.set_path(ex if path in EX_FIELDS else key, path, value)
    errors = validate(eid, ex, key)
    if errors:
        return {"saved": False, "errors": errors}

    layer = content.overrides()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    changed = []
    for path, value in clean.items():
        src = "exercises" if path in EX_FIELDS else "answer_key"
        old = _get(content.exercises()["exercises"][eid], path) if src == "exercises" else content.answer_key()[eid].get(path)
        if old == value:
            continue
        layer.setdefault(src, {}).setdefault(eid, {})[path] = value
        layer.setdefault("history", []).append({"exercise": eid, "at": now, "by": user, "field": path,
                                                "old": old, "new": value})
        changed.append(path)
    if changed:
        # Any change returns the exercise to draft until a teacher approves it again.
        layer.setdefault("exercises", {}).setdefault(eid, {})["status"] = "draft"
        layer.setdefault("meta", {}).pop(eid, None)
        _save(layer)
    return {"saved": True, "changed": changed, "errors": []}


def approve(eid: str, user: str) -> dict:
    errors = validate(eid)
    if errors:
        raise EditError("fix the errors before approving")
    layer = content.overrides()
    layer.setdefault("exercises", {}).setdefault(eid, {})["status"] = "approved"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    layer.setdefault("meta", {})[eid] = {"approved_by": user, "approved_at": now}
    layer.setdefault("history", []).append({"exercise": eid, "at": now, "by": user, "field": "status",
                                            "old": content.exercises()["exercises"][eid]["status"], "new": "approved"})
    _save(layer)
    return current(eid)


def revert(eid: str, user: str) -> dict:
    """Back to the repository version (history is kept)."""
    layer = content.overrides()
    for src in ("exercises", "answer_key", "meta"):
        layer.get(src, {}).pop(eid, None)
    layer.setdefault("history", []).append({"exercise": eid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": user,
                                            "field": "revert", "old": None, "new": None})
    _save(layer)
    return current(eid)


def export_yaml() -> str:
    """The changes only, to be applied to content/*.yaml in the repository."""
    layer = content.overrides()
    out = {"exercises.yaml": layer.get("exercises", {}), "answer_key.yaml": layer.get("answer_key", {}),
           "approvals": layer.get("meta", {})}
    head = ("# Content changes made in the teacher screen. Apply them to content/exercises.yaml and\n"
            "# content/answer_key.yaml in the repository (dotted keys are nested fields).\n")
    return head + yaml.safe_dump(out, allow_unicode=True, sort_keys=True)
