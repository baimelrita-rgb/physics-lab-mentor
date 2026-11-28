"""Class over time (UI doc · teacher screens · "class over time").

Built only from sessions the teacher already has: no extra storage.
- heatmap: group x rubric aspect (average of the confirmed score, else the suggested one)
- misconceptions: how many groups showed each one, and the share per lesson (trend)
- stages: time spent per stage, and how often it crossed the "stuck" threshold
- mastery: per knowledge card, from the rubric of finished sessions of exercises that teach it
Students are identified by the group label they typed when joining ("קבוצה א").
Individual student identity comes with the class roster (later stage).
"""
from __future__ import annotations

import statistics as st
import time

from . import content
from .session import STEPS, Session
from .teacher import MISCONCEPTIONS, RUBRIC, STATE_LABEL, STUCK_SECONDS, Lesson, misconceptions_of, rubric

FINISHED = {"RECHECK", "EXIT", "CLOSED"}
TIMED = ["THEORY", "PREDICT", "OBSERVE", "HYPOTHESIZE", "EVIDENCE", "REASON", "RECHECK", "EXIT"]
NO_CLASS = "ללא כיתה"


def class_names(lessons: list[Lesson]) -> list[dict]:
    out: dict[str, int] = {}
    for l in lessons:
        out[l.class_name or NO_CLASS] = out.get(l.class_name or NO_CLASS, 0) + 1
    return [{"name": k, "lessons": v} for k, v in sorted(out.items(), key=lambda x: (x[0] == NO_CLASS, x[0]))]


def stage_durations(s: Session, now: float) -> dict[str, float]:
    """Seconds spent in each state, from the session's own event log."""
    out: dict[str, float] = {}
    entered, state = None, None
    for e in s.events:
        if e["type"] == "session.opened":
            entered, state = e["at"], "THEORY"
        elif e["type"] == "state.changed" and entered is not None:
            out[state] = out.get(state, 0) + e["at"] - entered
            entered, state = e["at"], e["to"]
    if entered is not None and state != "CLOSED":
        out[state] = out.get(state, 0) + max(0.0, now - entered)
    return out


def final_scores(s: Session, closed: bool = False) -> list[int | None]:
    """Confirmed scores, else the suggested ones. Once the lesson is closed, an aspect the
    group never reached counts as 0 (it is no longer "not judged yet")."""
    sc = s.teacher_scores or rubric(s)
    return [0 if (x is None and closed) else x for x in sc]


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 2) if xs else None


def build(lessons: list[Lesson], sessions: dict[str, Session], class_name: str, days: int | None,
          now: float | None = None) -> dict:
    now = now if now is not None else time.time()
    since = now - days * 86400 if days else 0
    chosen = sorted([l for l in lessons if (l.class_name or NO_CLASS) == class_name and l.started >= since
                     and not l.planned], key=lambda l: l.started)
    exs = content.exercises()
    ss: list[tuple[Lesson, Session]] = [(l, sessions[i]) for l in chosen for i in l.session_ids if i in sessions]

    # ---------- heatmap ----------
    groups: dict[str, list[Session]] = {}
    closed_of = {s.id: l.closed for l, s in ss}
    for _, s in ss:
        groups.setdefault(s.label.strip() or "עמדה", []).append(s)
    heat = []
    for label, items in sorted(groups.items()):
        scored = [final_scores(s, closed_of[s.id]) for s in items]
        aspects = [_avg([sc[i] for sc in scored]) for i in range(len(RUBRIC))]
        heat.append({"label": label, "sessions": len(items), "finished": sum(s.state in FINISHED for s in items),
                     "aspects": aspects, "hints": _avg([s.hints_used for s in items]),
                     "confirmed": sum(s.teacher_scores is not None for s in items)})

    # ---------- misconceptions ----------
    per_lesson = [(l, [s for ll, s in ss if ll is l]) for l in chosen]
    mis = []
    for code, label in MISCONCEPTIONS.items():
        hit_groups = {s.label.strip() for _, s in ss if code in misconceptions_of(s)}
        trend = [{"lesson": l.id, "date": l.date or time.strftime("%Y-%m-%d", time.localtime(l.started)),
                  "share": round(sum(code in misconceptions_of(s) for s in items) / len(items), 2) if items else None}
                 for l, items in per_lesson]
        shares = [t["share"] for t in trend if t["share"] is not None]
        direction = None
        if len(shares) >= 2:
            half = len(shares) // 2
            a, b = st.mean(shares[:half]), st.mean(shares[half:])
            direction = "down" if b < a - 0.05 else "up" if b > a + 0.05 else "flat"
        if hit_groups:
            mis.append({"id": code, "label": label, "groups": len(hit_groups), "group_names": sorted(hit_groups),
                        "sessions": sum(code in misconceptions_of(s) for _, s in ss), "trend": trend,
                        "direction": direction})
    mis.sort(key=lambda m: -m["groups"])

    # ---------- stages ----------
    # For a closed lesson the clock stops at the session's last action, not at "now".
    durs = [stage_durations(s, max((e["at"] for e in s.events), default=now) if l.closed else now) for l, s in ss]
    hint_states: dict[str, int] = {}
    for _, s in ss:
        for e in s.events:
            if e["type"] == "hint.given":
                hint_states[e["state"]] = hint_states.get(e["state"], 0) + 1
    stages = []
    for state in TIMED:
        xs = [d[state] for d in durs if state in d]
        stages.append({"state": state, "label": STATE_LABEL[state], "sessions": len(xs),
                       "median_s": round(st.median(xs)) if xs else None, "max_s": round(max(xs)) if xs else None,
                       "stuck": sum(x > STUCK_SECONDS for x in xs), "hints": hint_states.get(state, 0)})

    # ---------- mastery per knowledge card ----------
    cards = exs["knowledge_cards"]
    mastery = []
    for cid, card in cards.items():
        def score(s: Session):
            sc = [x for x in final_scores(s, closed_of[s.id]) if x is not None]
            return sum(sc) / (2 * len(RUBRIC)) if sc else None
        rel = [s for _, s in ss if cid in exs["exercises"][s.exercise_id]["cards"]
               and (s.state in FINISHED or s.teacher_scores is not None or closed_of[s.id])]
        by_group = {label: _avg([score(s) for s in items if s in rel]) for label, items in groups.items()}
        mastery.append({"id": cid, "title": card["title"], "class": _avg([score(s) for s in rel]),
                        "sessions": len(rel), "groups": by_group})

    return {
        "class_name": class_name, "days": days, "threshold_s": STUCK_SECONDS,
        "lessons": [{"id": l.id, "date": l.date or time.strftime("%Y-%m-%d", time.localtime(l.started)),
                     "exercise": f'{exs["exercises"][l.exercise_id]["title"]}', "number": int(l.exercise_id.split("-")[-1]),
                     "groups": len(l.session_ids)} for l in chosen],
        "aspects": RUBRIC, "heatmap": heat, "misconceptions": mis, "stages": stages, "mastery": mastery,
        "steps": STEPS,
    }
