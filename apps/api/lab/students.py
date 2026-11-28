"""Per-student view over time, from the sessions the student was a member of."""
from __future__ import annotations

import time

from . import content
from .classview import FINISHED, NO_CLASS, _avg, final_scores
from .session import Session
from .teacher import MISCONCEPTIONS, RUBRIC, STATE_LABEL, Lesson, misconceptions_of


def _date(l: Lesson) -> str:
    return l.date or time.strftime("%Y-%m-%d", time.localtime(l.started))


def _rows(lessons: list[Lesson], sessions: dict[str, Session], class_name: str):
    for l in sorted(lessons, key=lambda x: x.started):
        if (l.class_name or NO_CLASS) != class_name or l.planned:
            continue
        for sid in l.session_ids:
            if sid in sessions:
                yield l, sessions[sid]


def _score01(sc: list) -> float | None:
    xs = [x for x in sc if x is not None]
    return sum(xs) / (2 * len(RUBRIC)) if xs else None


def overview(lessons, sessions, class_name: str, roster: list[dict]) -> dict:
    rows = list(_rows(lessons, sessions, class_name))
    out = []
    for st in roster:
        mine = [(l, s) for l, s in rows if st["id"] in s.members]
        scored = [final_scores(s, l.closed) for l, s in mine]
        mis = sorted({m for _, s in mine for m in misconceptions_of(s)})
        trend = [_score01(sc) for sc in scored]
        out.append({
            "id": st["id"], "name": st["name"], "active": st["active"], "lessons": len(mine),
            "aspects": [_avg([sc[i] for sc in scored]) for i in range(len(RUBRIC))],
            "finished": sum(s.state in FINISHED for _, s in mine),
            "hints": _avg([s.hints_used for _, s in mine]),
            "misconceptions": [{"id": m, "label": MISCONCEPTIONS.get(m, m)} for m in mis],
            "trend": [round(x, 2) if x is not None else None for x in trend],
            "last": _date(mine[-1][0]) if mine else None,
        })
    unassigned = sum(1 for _, s in rows if not s.members)
    return {"class_name": class_name, "aspects": RUBRIC, "students": out, "unassigned_sessions": unassigned,
            "sessions": len(rows)}


def detail(lessons, sessions, class_name: str, roster: list[dict], student_id: str) -> dict | None:
    st = next((x for x in roster if x["id"] == student_id), None)
    if not st:
        return None
    names = {x["id"]: x["name"] for x in roster}
    exs = content.exercises()
    items = []
    for l, s in _rows(lessons, sessions, class_name):
        if student_id not in s.members:
            continue
        sc = final_scores(s, l.closed)
        items.append({
            "lesson": l.id, "session": s.id, "date": _date(l),
            "number": int(s.exercise_id.split("-")[-1]), "title": exs["exercises"][s.exercise_id]["title"],
            "group": s.label, "partners": [names.get(m, "?") for m in s.members if m != student_id],
            "stage": STATE_LABEL[s.state], "finished": s.state in FINISHED,
            "scores": sc, "confirmed": s.teacher_scores is not None, "total": sum(x for x in sc if x is not None),
            "hints": s.hints_used,
            "misconceptions": [{"id": m, "label": MISCONCEPTIONS.get(m, m)} for m in misconceptions_of(s)],
            "teacher_note": s.teacher_note,
        })
    mastery = []
    for cid, card in exs["knowledge_cards"].items():
        vals = [_score01(i["scores"]) for i in items if cid in exs["exercises"][f'EX-{i["number"]:02d}']["cards"]]
        mastery.append({"id": cid, "title": card["title"], "value": _avg(vals), "sessions": len([v for v in vals if v is not None])})
    return {"student": st, "aspects": RUBRIC, "sessions": items, "mastery": mastery,
            "averages": [_avg([i["scores"][k] for i in items]) for k in range(len(RUBRIC))]}
