"""Deterministic diagnosis (technical design · tutor stage 2: evidence check).

The answer key is read here and only here. The result has two parts:
- `student`: what the student may see (an outcome code and an approved message);
- `teacher`: full detail for the teacher screen and the log.
The LLM never decides whether the student is right.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import content

MSG = {
    "supported": "הנימוק שלכם נשען על ראיות. עכשיו בדקו אם הוא מחזיק גם בהמשך ההקלטה.",
    "insufficient_valid": "נימוק טוב: זיהיתם שחסרה ראיה תקפה. בדקו מה קורה בהמשך ההקלטה.",
    "unsupported": "ההשערה עדיין לא מבוססת מספיק. איזו קריאה נוספת תעזור להכריע?",
    "not_matching": "הראיות שאספתם עוד לא מתיישבות עם ההשערה. בדקו ערוץ נוסף.",
    "insufficient_unjustified": "מה בדיוק חסר כדי להכריע? צטטו קריאה שמראה את החוסר.",
}


@dataclass
class Result:
    outcome: str                 # supported | insufficient_valid | unsupported | misconception | not_matching | insufficient_unjustified
    message: str
    passed: bool
    misconception: str | None = None
    teacher: dict = field(default_factory=dict)

    def student_view(self) -> dict:
        return {"outcome": self.outcome, "message": self.message, "passed": self.passed}


def check_theory(exercise_id: str, choice: int) -> bool:
    return content.answer_key()[exercise_id]["check_answer"] == choice


def _satisfied(item: dict, readings: list[dict]) -> bool:
    lo, hi = item["window"]
    return any(
        r["channel"] in item["any_of"] and lo <= r["t"] <= hi and r["quality"] == "ok"
        for r in readings
    )


def evaluate(exercise_id: str, hypothesis: str | None, cited: list[dict]) -> Result:
    key = content.answer_key()[exercise_id]
    redirects = content.answer_key()["misconception_redirects"]
    missing = [i["label"] for i in key["evidence"] if not _satisfied(i, cited)]
    bad_quality = [r for r in cited if r["quality"] != "ok"]
    detail = {"hypothesis": hypothesis, "cause": key["cause"], "missing_evidence": missing,
              "cited": [r["id"] for r in cited], "bad_quality_cited": [r["id"] for r in bad_quality]}

    # A conclusion drawn from a stale or missing reading (M-03 / M-02), unless that is the point.
    if bad_quality and hypothesis not in ("H-STALE", "H-MISSING", "H-INSUFFICIENT"):
        mid = "M-03" if any(r["quality"] == "stale" for r in bad_quality) else "M-02"
        return Result("misconception", redirects[mid], False, mid, detail)

    if hypothesis == "H-INSUFFICIENT":
        if bad_quality:
            return Result("insufficient_valid", MSG["insufficient_valid"], True, None, detail)
        return Result("insufficient_unjustified", MSG["insufficient_unjustified"], False, None, detail)

    if hypothesis == key["cause"]:
        if not missing:
            return Result("supported", MSG["supported"], True, None, detail)
        return Result("unsupported", MSG["unsupported"], False, None, detail)

    mid = key.get("misconceptions", {}).get(hypothesis)
    if mid:
        return Result("misconception", redirects[mid], False, mid, detail)
    return Result("not_matching", MSG["not_matching"], False, None, detail)
