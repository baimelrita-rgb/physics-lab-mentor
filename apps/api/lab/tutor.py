"""Tutor: picks the approved text for a move, asks the gateway to phrase it, falls back safely.

The move and its approved text are chosen in code (session / diagnosis). This module only
decides what the LLM may see: the move, the approved text, facts the student already saw
(their saved readings), the student's own text and the exercise misconception list.
"""
from __future__ import annotations

from . import content
from .llm import Gateway, LLMError, MISC_TEXT

OFF_TOPIC = "השאלה הזו לא קשורה לתרגיל. בואו נחזור לגרף: מה עוד צריך לבדוק כדי להכריע?"
ANSWER_REQUEST = "את התשובה תמצאו בנתונים, ואני אעזור לכם להגיע אליה. איזו קריאה עוד חסרה לכם?"
UNCLEAR = "לא בטוח שהבנתי. אפשר לנסח את השאלה אחרת, או לבחור אחת מהתשובות המהירות?"
GENERIC_PROBE = {
    "HYPOTHESIZE": "מה לדעתכם גרם לשינוי, ואיזו מדידה תוכל לבדוק את זה?",
    "EVIDENCE": "איזה ערוץ יעזור להכריע בין ההשערות, ומה הייתם מצפים לראות בו?",
    "REASON": "על אילו שתי קריאות הנימוק שלכם נשען?",
    "RECHECK": "מה קורה בהמשך ההקלטה, והאם זה מתיישב עם המסקנה שלכם?",
}


def leak_terms(exercise_id: str) -> list[str]:
    key = content.answer_key()[exercise_id]
    return list(key.get("leak_terms", []))


def facts_of(session) -> list[str]:
    out = []
    for r in session.readings:
        v = "חסר" if r["value"] is None else f"{r['value']:g} {r['unit']}"
        out.append(f"קריאה ששמרתם: {r['name']} בשנייה {r['t']} = {v}" + ("" if r["quality"] == "ok" else f" ({r['quality']})"))
    return out


class Tutor:
    def __init__(self, gateway: Gateway | None = None):
        self.gw = gateway or Gateway()

    @property
    def live(self) -> bool:
        return self.gw.available

    def say(self, session, move: str, approved: str, student_text: str = "") -> dict:
        """Phrase `approved` for this student. Always returns {text, chips, source, failures}."""
        mis = [f"{m}: {MISC_TEXT[m]}" for m in session.ex.get("misconceptions_shown", [])] or list(MISC_TEXT.values())
        if not self.live:
            return {"text": approved, "chips": [], "source": "static", "failures": []}
        out, fails = self.gw.phrase(move=move, state=session.state, approved=approved, facts=facts_of(session),
                                    student_text=student_text, forbidden=leak_terms(session.exercise_id),
                                    misconceptions=mis)
        if out is None:
            return {"text": approved, "chips": [], "source": "static", "failures": fails}
        return {"text": out["text"].strip(), "chips": out.get("chips", [])[:3], "source": "llm", "failures": []}

    def classify(self, session, text: str) -> dict | None:
        if not self.live:
            return None
        try:
            return self.gw.classify(text, state=session.state, codes=session.ex["hypothesis_options"],
                                    channels=[content.channel_index()[k]["name"] for k in session.open_channels])
        except LLMError:
            return None

    def answer(self, session, text: str) -> dict:
        """A free question from the AskField. Returns the mentor reply and the classification."""
        cls = self.classify(session, text)
        intent = cls["intent"] if cls else "question"
        if intent == "off_topic":
            return {"text": OFF_TOPIC, "chips": [], "source": "static", "intent": intent, "failures": []}
        if intent == "answer_request":
            reply = self.say(session, "redirect", ANSWER_REQUEST, text)
            return {**reply, "intent": intent}
        if intent == "unclear":
            return {"text": UNCLEAR, "chips": [], "source": "static", "intent": intent, "failures": []}
        base = GENERIC_PROBE.get(session.state, GENERIC_PROBE["EVIDENCE"])
        reply = self.say(session, "probe", base, text)
        return {**reply, "intent": intent, "classification": cls}
