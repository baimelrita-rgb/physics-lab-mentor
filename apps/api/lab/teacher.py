"""Teacher side: lessons, live cards, alerts and the suggested rubric (UI doc · live lesson).

This module may read the answer key: the teacher is allowed to see it.
"""
from __future__ import annotations

import os
import random
import time
import uuid
from dataclasses import dataclass, field

from . import content, envelope
from .session import HINT_QUOTA, STEP_OF, STEPS, Session

# A station is "stuck" after this long in one investigation step (UI doc: max_dwell).
STUCK_SECONDS = float(os.environ.get("STUCK_SECONDS", "300"))
INVESTIGATION = {"HYPOTHESIZE", "EVIDENCE", "REASON"}
RUBRIC = ["השערה ותחזית", "בחירת בדיקה", "איכות ראיה", "מסקנה ובדיקה חוזרת"]
MISCONCEPTIONS = {
    "M-01": "כל האטה היא ירידת תדר",
    "M-02": "ערך חסר פירושו אפס",
    "M-03": "מספר מוצג הוא עדכני",
    "M-04": "מומנט והספק כשתי ראיות",
    "M-05": "פקודת תדר = תדר יציאה",
    "M-06": "זרם רשת = זרם מנוע",
}
STATE_LABEL = {"THEORY": "רקע", "PREDICT": "תחזית", "OBSERVE": "צפייה", "HYPOTHESIZE": "השערה",
               "EVIDENCE": "ראיות", "REASON": "נימוק", "RECHECK": "בדיקה חוזרת", "EXIT": "שאלת יציאה",
               "CLOSED": "הושלם"}


@dataclass
class Lesson:
    exercise_id: str
    clock: callable = time.time
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    code: str = field(default_factory=lambda: f"{random.randint(0, 999999):06d}")
    started: float = 0.0
    session_ids: list[str] = field(default_factory=list)
    closed: bool = False
    owner: str = ""             # teacher username; "" = demo mode
    # Lesson prep (UI doc: teacher screens, lesson prep wizard).
    class_name: str = ""
    date: str = ""
    stations: int = 1
    hint_quota: int = HINT_QUOTA
    allow_ask: bool = True
    deduction: str = "none"     # "none" | "per_hint": one point off the total per hint the student asked for
    planned: bool = False       # saved for later; stations cannot join until the teacher opens it
    closed_at: float = 0.0      # when the lesson ended (by the teacher or automatically)

    def __post_init__(self):
        self.started = self.clock()


def evidence_channels(exercise_id: str) -> set[str]:
    key = content.answer_key()[exercise_id]
    return {c for item in key["evidence"] for c in item["any_of"]}


def misconceptions_of(s: Session) -> list[str]:
    out = [a["misconception"] for a in s.attempts if a.get("misconception")]
    # Misconceptions the classifier found in the student's own words (teacher information only).
    for item in [a.get("classification") for a in s.attempts] + [q.get("classification") for q in s.asks]:
        m = (item or {}).get("misconception")
        if m and m != "none" and (item or {}).get("intent") != "unclear" and m not in out:
            out.append(m)
    # Brain 1: M-01 is also detected when H-FREQ is chosen without an output-frequency channel open.
    if s.hypothesis == "H-FREQ" and "f_drive_hz" not in s.open_channels and "M-01" not in out:
        out.append("M-01")
    return out


def rubric(s: Session) -> list[int | None]:
    """Suggested score per aspect, 0-2, or None while it cannot be judged yet. The teacher confirms."""
    ev = evidence_channels(s.exercise_id) - set(s.ex["initial_channels"])
    passed = any(a["passed"] for a in s.attempts)

    pred = None
    if STEP_OF[s.state] > 1:
        dirs = (s.prediction or {}).get("directions", {})
        pred = 2 if (set(dirs) & evidence_channels(s.exercise_id)) and s.hypothesis else (1 if s.prediction else 0)

    test = None
    if s.state in INVESTIGATION | {"RECHECK", "EXIT", "CLOSED"}:
        opens = [o for o in s.channel_opens if o["channel"] in ev]
        if not ev:
            test = 2
        elif opens:
            test = 2 if opens[0]["hints_used"] < 2 else 1
        elif s.state not in ("HYPOTHESIZE", "EVIDENCE"):
            test = 0

    quality = None
    if s.attempts:
        bad = [a for a in s.attempts if a.get("misconception") in ("M-02", "M-03")]
        quality = 0 if bad and not passed else (1 if bad else 2)

    concl = None
    if s.attempts:
        rechecked = any(r["t"] > s.ex["stop_s"] for r in s.readings) and s.state in ("EXIT", "CLOSED")
        concl = (2 if rechecked else 1) if passed else 0
    return [pred, test, quality, concl]


CHANNEL_NAME = lambda k: content.channel_index()[k]["name"]  # noqa: E731


def safety_events(s: Session) -> list[dict]:
    """Envelope events the station has reached so far (in a recording: up to the second shown)."""
    upto = s.visible_t()
    return [e for e in envelope.for_recording(s.recording) if e["t"] <= upto]


def alerts(s: Session) -> list[dict]:
    out = []
    for e in safety_events(s):
        unit = content.channel_index()[e["channel"]]["unit"]
        where = "בהקלטה, חריגה מדומה" if s.recording.data_origin == "synthetic" else "בעמדה"
        verb = "מעל" if e["limit"] is not None and e["value"] >= e["limit"] else "מתחת ל־"
        out.append({"kind": "safety" if e["level"] == "stop" else "safety_warn",
                    "title": f"בטיחות {e['rule']}" + ("" if e["level"] == "stop" else " · התקרבות לסף"),
                    "text": f"{s.label}: {CHANNEL_NAME(e['channel'])} {e['value']:g} {unit} {verb} {e['limit']:g} {unit}"
                            f" ({where}, שנייה {e['t']}). ערך הסף מוצע וממתין לאישור תלם.",
                    "suggest": ("בעמדה חיה: עצרו את המנוע בלחצן העצירה ובדקו את העומס לפני שממשיכים. "
                                "בהקלטה: אפשר לשאול את הקבוצה מה היה קורה בעמדה אמיתית.")})
    if s.state in INVESTIGATION and s.time_in_state() > STUCK_SECONDS and not s.paused:
        secs = int(s.time_in_state())
        extra = "" if len(s.open_channels) > len(s.ex["initial_channels"]) else ", בלי ערוץ פתוח נוסף"
        out.append({"kind": "stuck", "title": "תקוע",
                    "text": f"{s.label}: {secs // 60}:{secs % 60:02d} דקות בשלב {STATE_LABEL[s.state]}{extra}.",
                    "suggest": "שאלו: איזו מדידה תבדיל בין שתי ההשערות שלכם?"})
    if s.hint_quota and s.hints_used >= s.hint_quota:
        out.append({"kind": "hint3", "title": "הגיע לרמז 3", "text": f"{s.label} השתמש ברמז האחרון.",
                    "suggest": "בדקו בעל פה אם הקבוצה יודעת מה היא מחפשת בגרף."})
    off = [q for q in s.asks if q["intent"] == "off_topic"]
    if off:
        out.append({"kind": "offtopic", "title": "מחוץ לתחום",
                    "text": f"{s.label} שאל שאלה שאינה קשורה לתרגיל. הוחזר לתרגיל.",
                    "suggest": "בדקו אם הקבוצה תקועה ומחפשת דרך לצאת מהמשימה."})
    for m in misconceptions_of(s)[-1:]:
        out.append({"kind": "misconception", "title": f"תפיסה שגויה {m}",
                    "text": f"{s.label}: {MISCONCEPTIONS[m]}.",
                    "suggest": content.answer_key()["misconception_redirects"][m]})
    return out


URGENCY = {"safety": -1, "stuck": 0, "hint3": 1}


def deduction(s: Session, policy: str) -> int:
    return s.hint_sources.count("student") if policy == "per_hint" else 0


def card(s: Session, index: int, policy: str = "none") -> dict:
    al = alerts(s)
    urgency = min([URGENCY.get(a["kind"], 2) for a in al], default=3)
    hyp = content.exercises()["hypotheses"].get(s.hypothesis) if s.hypothesis else None
    flag = {-1: "בטיחות", 0: "תקוע", 1: "רמז 3"}.get(urgency) or ("הושלם" if s.state == "CLOSED" else None)
    scores = s.teacher_scores or rubric(s)
    return {
        "id": s.id, "label": s.label, "members": s.members, "index": index, "state": s.state, "stage": STATE_LABEL[s.state],
        "step": STEP_OF[s.state], "seconds_in_state": int(s.time_in_state()), "paused": s.paused,
        "hypothesis": s.hypothesis, "hypothesis_label": hyp, "hints_used": s.hints_used, "quota": s.hint_quota,
        "flag": flag, "urgency": urgency, "alerts": al, "rubric": scores, "confirmed": s.teacher_scores is not None,
        "deduction": deduction(s, policy),
        "total": max(0, sum(x for x in scores if x is not None) - deduction(s, policy)),
    }


def live(lesson: Lesson, sessions: dict[str, Session]) -> dict:
    ss = [sessions[i] for i in lesson.session_ids if i in sessions]
    cards = [card(s, i + 1, lesson.deduction) for i, s in enumerate(ss)]
    # Order: safety, stuck, quota used up, then station number (UI doc · live lesson).
    cards.sort(key=lambda c: (c["urgency"], c["index"]))
    counts: dict[str, set] = {}
    for s in ss:
        for m in misconceptions_of(s):
            counts.setdefault(m, set()).add(s.id)
    ex = content.exercises()["exercises"][lesson.exercise_id]
    return {
        "lesson": {"id": lesson.id, "code": lesson.code, "exercise_id": lesson.exercise_id,
                   "title": ex["title"], "subtitle": ex["subtitle"], "status": ex["status"],
                   "stop_s": ex["stop_s"], "elapsed": int((lesson.closed_at or lesson.clock()) - lesson.started),
                   "closed": lesson.closed},
        "cards": cards,
        "alerts": [dict(a, station=c["label"], session=c["id"]) for c in cards for a in c["alerts"]],
        "rubric_aspects": RUBRIC,
        "misconceptions": sorted(({"id": m, "label": MISCONCEPTIONS[m], "count": len(v)} for m, v in counts.items()),
                                 key=lambda x: -x["count"]),
        "steps": STEPS,
    }


def detail(s: Session) -> dict:
    """Everything about one station, including the answer key (teacher only)."""
    key = content.answer_key()[s.exercise_id]
    hyp = content.exercises()["hypotheses"]
    t0 = s.events[0]["at"] if s.events else 0
    names = {k: v["name"] for k, v in content.channel_index().items()}
    pred = None
    if s.prediction:
        pred = {"directions": {names.get(k, k): v for k, v in s.prediction["directions"].items()},
                "text": s.prediction["text"]}

    def event(e: dict) -> dict:
        out = {"t": int(e["at"] - t0), **{k: v for k, v in e.items() if k != "at"}}
        if "to" in out:
            out["to"] = STATE_LABEL.get(out["to"], out["to"])
        if "channel" in out:
            out["channel"] = names.get(out["channel"], out["channel"])
        return out
    return {
        "id": s.id, "label": s.label, "state": s.state, "stage": STATE_LABEL[s.state],
        "expected": {"cause": key["cause"], "cause_label": hyp[key["cause"]], "conclusion": key["conclusion"]},
        "prediction": pred, "theory_answer": s.theory_answer,
        "hypothesis_label": hyp.get(s.hypothesis) if s.hypothesis else None,
        "readings": s.readings, "attempts": [{k: v for k, v in a.items() if k != "detail"} | {"missing": a["detail"]["missing_evidence"]}
                                              for a in s.attempts],
        "exit_answer": s.exit_answer, "rubric": rubric(s), "rubric_aspects": RUBRIC,
        "confirmed_scores": s.teacher_scores, "teacher_note": s.teacher_note,
        "asks": s.asks, "hints": [{"level": i + 1, "text": t, "by": s.hint_sources[i]} for i, t in enumerate(s.hint_texts)],
        "timeline": [event(e) for e in s.events],
    }


def confirm_scores(s: Session, scores: list, note: str = ""):
    if len(scores) != len(RUBRIC) or any(x not in (0, 1, 2) for x in scores):
        raise ValueError("four scores, each 0, 1 or 2")
    s.teacher_scores = list(scores)
    s.teacher_note = note.strip()[:300]
    s._log("teacher.scored", scores=s.teacher_scores, suggested=rubric(s), note=s.teacher_note)


def export_csv(lesson: Lesson, sessions: dict[str, Session]) -> str:
    """Lesson grades as CSV (UTF-8 with BOM so Excel shows Hebrew)."""
    import csv
    import io
    hyp = content.exercises()["hypotheses"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["עמדה", "תרגיל", "שלב אחרון", "השערה", "רמזים", "קריאות", "ניסיונות נימוק",
                *[f"{a} (מוצע)" for a in RUBRIC], *[f"{a} (מאושר)" for a in RUBRIC],
                "ניכוי רמזים", "סה״כ", "ציון אושר", "תפיסות שגויות", "שאלת יציאה", "הערת מורה"])
    from .security import csv_safe
    for sid in lesson.session_ids:
        s = sessions.get(sid)
        if not s:
            continue
        sug = rubric(s)
        final = s.teacher_scores or sug
        w.writerow([csv_safe(x) for x in [s.label, s.exercise_id, STATE_LABEL[s.state], hyp.get(s.hypothesis, "") if s.hypothesis else "",
                    s.hints_used, len(s.readings), len(s.attempts),
                    *["" if x is None else x for x in sug],
                    *(s.teacher_scores or [""] * len(RUBRIC)),
                    deduction(s, lesson.deduction),
                    max(0, sum(x for x in final if x is not None) - deduction(s, lesson.deduction)), "כן" if s.teacher_scores else "לא",
                    " ".join(misconceptions_of(s)), s.exit_answer or "", s.teacher_note]])
    return "\ufeff" + buf.getvalue()
