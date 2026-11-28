"""Station session: the exercise state machine, the time gate and the student's work.

Transitions are guarded in code, not in a prompt (technical design §5).
The student view never includes teacher_* data or the answer key.
"""
from __future__ import annotations

import itertools
import json
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import content, diagnosis
from .ingest import Recording

STATES = ["THEORY", "PREDICT", "OBSERVE", "HYPOTHESIZE", "EVIDENCE", "REASON",
          "RECHECK", "EXIT", "CLOSED"]
# Six main steps on the stepper (design: student screen).
STEP_OF = {"THEORY": 0, "PREDICT": 1, "OBSERVE": 2, "HYPOTHESIZE": 3, "EVIDENCE": 4,
           "REASON": 5, "RECHECK": 5, "EXIT": 5, "CLOSED": 5}
STEPS = ["רקע", "תחזית", "צפייה", "השערה", "ראיות", "מסקנה"]
READING_STATES = {"HYPOTHESIZE", "EVIDENCE", "REASON", "RECHECK"}
HINT_STATES = {"HYPOTHESIZE", "EVIDENCE", "REASON", "RECHECK"}
HINT_QUOTA = 3
MIN_READINGS = 2

MENTOR_TEXT = {
    "HYPOTHESIZE": "מה לדעתכם גרם לשינוי? בחרו השערה אחת.",
    "EVIDENCE": "איזה ערוץ יבדוק את ההשערה שלכם? פתחו ערוץ, ולחצו על הגרף כדי לשמור קריאות לפני השינוי ואחריו.",
    "REASON": "כתבו נימוק קצר וצטטו לפחות שתי קריאות מהמגש. אפשר גם לענות ״אין די ראיות״.",
    "CLOSED": "סיימתם את התרגיל. המורה יראה את היומן שלכם.",
}


def exercise_number(exercise_id: str) -> str:
    return f"תרגיל {int(exercise_id.split('-')[-1])}"


class GuardError(Exception):
    """A transition or action that the current state does not allow (STATE_GUARD_FAILED)."""


@dataclass
class Session:
    exercise_id: str
    recording: Recording
    clock: Callable[[], float] = time.time
    log_path: Path | None = None
    replay_speed: float = 1.0
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = "THEORY"
    state_rev: int = 0
    paused: bool = False
    theory_answer: dict | None = None
    prediction: dict | None = None
    hypothesis: str | None = None
    open_channels: list[str] = field(default_factory=list)
    readings: list[dict] = field(default_factory=list)
    hints_used: int = 0
    feedback: dict | None = None
    attempts: list[dict] = field(default_factory=list)
    exit_answer: str | None = None
    label: str = "עמדה 1"
    lesson_id: str | None = None
    hint_quota: int = HINT_QUOTA                            # set by the teacher in lesson prep (0-3)
    allow_ask: bool = True                                  # free question to the mentor allowed
    members: list[str] = field(default_factory=list)        # roster ids of the students in this group
    token: str = ""                                         # group token (cookie); never sent in student_view
    teacher_message: str | None = None
    hint_sources: list[str] = field(default_factory=list)   # "student" | "teacher", per level
    hint_texts: list[str] = field(default_factory=list)     # text actually shown, per level
    asks: list[dict] = field(default_factory=list)          # free questions and mentor replies
    mentor_reply: dict | None = None
    tutor: object = None                                    # lab.tutor.Tutor, or None for static texts only
    teacher_scores: list | None = None                      # rubric confirmed by the teacher (0-2 per aspect)
    teacher_note: str = ""
    channel_opens: list[dict] = field(default_factory=list)  # {channel, hints_used}
    events: list[dict] = field(default_factory=list)          # timeline for the teacher
    state_entered: float = 0.0
    _observe_started: float | None = None
    _recheck_started: float | None = None
    _paused_at: float | None = None
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def __post_init__(self):
        ex = self.ex
        self.open_channels = list(ex["initial_channels"])
        self.state_entered = self.clock()
        # Random alias per session, so students cannot pass answers by run name (Brain 3).
        self.alias = f"הרצה {random.choice('אבגדהזחטכלמנסעפקרשת')}־{random.randint(1, 9)}"
        self._log("session.opened", exercise=self.exercise_id, recording=self.recording.run_id)

    # ---------- helpers ----------
    @property
    def ex(self) -> dict:
        return content.exercises()["exercises"][self.exercise_id]

    def _log(self, type_: str, **payload):
        self.events.append({"at": self.clock(), "state": self.state, "type": type_, **payload})
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"session": self.id, "ts": time.time(), "state": self.state,
                                    "type": type_, **payload}, ensure_ascii=False) + "\n")

    def _require(self, *states: str):
        if self.state not in states:
            raise GuardError(f"not allowed in {self.state}")
        if self.paused:
            raise GuardError("paused by teacher")

    def _go(self, new: str):
        if new == "RECHECK" and self.ex["stop_s"] >= self.recording.duration:
            new = "EXIT"                 # nothing left to play after the stop point (EX-05)
        old, self.state = self.state, new
        self.state_rev += 1
        self.state_entered = self.clock()
        self.teacher_message = None
        self.mentor_reply = None
        if new == "OBSERVE":
            self._observe_started = self.clock()
        if new == "RECHECK":
            self._recheck_started = self.clock()
        self._log("state.changed", **{"from": old, "to": new})

    # ---------- time gate ----------
    def visible_t(self) -> int:
        """Last second of the recording the student may see now (-1 = nothing yet)."""
        stop, end = self.ex["stop_s"], self.recording.duration
        if self.state in ("THEORY", "PREDICT"):
            return -1
        now = self._paused_at if self._paused_at is not None else self.clock()   # replay freezes while paused
        if self.state == "OBSERVE":
            elapsed = (now - self._observe_started) * self.replay_speed
            return min(stop, int(elapsed))
        if self.state in ("HYPOTHESIZE", "EVIDENCE", "REASON"):
            return stop
        elapsed = (now - (self._recheck_started or now)) * self.replay_speed
        return min(end, stop + int(elapsed))

    def time_in_state(self) -> float:
        return self.clock() - self.state_entered

    # ---------- teacher actions ----------
    def pause(self):
        if not self.paused:
            self.paused, self._paused_at = True, self.clock()
            self._log("teacher.paused")

    def resume(self):
        if self.paused:
            gap = self.clock() - self._paused_at
            for attr in ("_observe_started", "_recheck_started"):
                if getattr(self, attr) is not None:
                    setattr(self, attr, getattr(self, attr) + gap)
            self.paused, self._paused_at = False, None
            self._log("teacher.resumed")

    def teacher_hint(self) -> str:
        if self.state not in HINT_STATES:
            raise GuardError(f"no hints in {self.state}")
        if self.hints_used >= len(self.ex["hints"]):
            raise GuardError("no hints left")
        self.hints_used += 1
        self.hint_sources.append("teacher")
        text = self.ex["hints"][self.hints_used - 1]       # the teacher's choice: approved text as-is
        self.hint_texts.append(text)
        self._log("hint.given", level=self.hints_used, by="teacher", source="static", text=text)
        return text

    def send_message(self, text: str):
        text = text.strip()[:200]
        if not text:
            raise GuardError("empty message")
        self.teacher_message = text
        self._log("teacher.message", text=text)

    # ---------- actions ----------
    def answer_theory(self, choice: int) -> bool:
        self._require("THEORY")
        ok = diagnosis.check_theory(self.exercise_id, choice)
        self.theory_answer = {"choice": choice, "correct": ok}
        self._log("theory.answered", choice=choice, correct=ok)
        return ok

    def submit_prediction(self, directions: dict[str, str], text: str = ""):
        self._require("PREDICT")
        allowed = set(self.ex["predict"]["channels"])
        clean = {k: v for k, v in directions.items() if k in allowed and v in ("up", "down", "same")}
        if not clean and not text.strip():
            raise GuardError("empty prediction")
        self.prediction = {"directions": clean, "text": text.strip()[:300]}
        self._log("prediction.submitted", **self.prediction)

    def choose_hypothesis(self, code: str):
        self._require("HYPOTHESIZE", "EVIDENCE", "REASON")
        if code not in self.ex["hypothesis_options"]:
            raise GuardError("unknown hypothesis")
        self.hypothesis = code
        self._log("hypothesis.chosen", code=code)

    def open_channel(self, key: str, expectation: str | None = None):
        self._require("OBSERVE", "HYPOTHESIZE", "EVIDENCE", "REASON", "RECHECK")
        if key not in self.ex["openable_channels"] and key not in self.ex["initial_channels"]:
            raise GuardError("channel not available in this exercise")
        if key not in self.open_channels:
            self.open_channels.append(key)
            self.channel_opens.append({"channel": key, "hints_used": self.hints_used})
            self._log("channel.opened", channel=key, expectation=expectation, hints_used=self.hints_used)

    def close_channel(self, key: str):
        if key in self.open_channels and key not in self.ex["initial_channels"]:
            self.open_channels.remove(key)
            self._log("channel.closed", channel=key)

    def add_reading(self, channel: str, t: int) -> dict:
        self._require(*READING_STATES)
        if channel not in self.open_channels:
            raise GuardError("channel is not open")
        if not 0 <= t <= self.visible_t():
            raise GuardError("that second is not visible yet")
        r = {"id": f"r{next(self._ids)}", "channel": channel, "t": t, **self._point(channel, t)}
        self.readings.append(r)
        self._log("reading.saved", **r)
        return r

    def remove_reading(self, rid: str):
        self.readings = [r for r in self.readings if r["id"] != rid]

    def request_hint(self) -> str:
        self._require(*HINT_STATES)
        if self.hints_used >= self.hint_quota:
            raise GuardError("no hints left")
        self.hints_used += 1
        self.hint_sources.append("student")
        approved = self.ex["hints"][self.hints_used - 1]
        said = self._say(f"hint_level_{self.hints_used}", approved)
        self.hint_texts.append(said["text"])
        self._log("hint.given", level=self.hints_used, by="student", source=said["source"],
                  text=said["text"], failures=said["failures"])
        return said["text"]

    def ask(self, text: str) -> dict:
        """A free question in the mentor's AskField (UI doc: up to 300 characters)."""
        self._require(*HINT_STATES)
        if not self.allow_ask:
            raise GuardError("free questions are off in this lesson")
        text = text.strip()[:300]
        if not text:
            raise GuardError("empty question")
        if self.tutor:
            reply = self.tutor.answer(self, text)
        else:
            from .tutor import GENERIC_PROBE
            reply = {"text": GENERIC_PROBE.get(self.state, GENERIC_PROBE["EVIDENCE"]), "chips": [],
                     "source": "static", "intent": "question", "failures": []}
        entry = {"q": text, "a": reply["text"], "chips": reply.get("chips", []), "intent": reply["intent"],
                 "source": reply["source"], "state": self.state,
                 "classification": reply.get("classification")}
        self.asks.append(entry)
        self.mentor_reply = {"text": reply["text"], "chips": reply.get("chips", [])}
        self._log("student.asked", **entry, failures=reply.get("failures", []))
        return entry

    def _say(self, move: str, approved: str, student_text: str = "") -> dict:
        if self.tutor:
            return self.tutor.say(self, move, approved, student_text)
        return {"text": approved, "chips": [], "source": "static", "failures": []}

    def submit_reason(self, text: str, cited_ids: list[str]) -> dict:
        self._require("REASON")
        cited = [r for r in self.readings if r["id"] in cited_ids]
        if len(cited) < MIN_READINGS and self.hypothesis != "H-INSUFFICIENT":
            raise GuardError(f"cite at least {MIN_READINGS} readings")
        res = diagnosis.evaluate(self.exercise_id, self.hypothesis, cited)
        text = text.strip()[:300]
        # The classifier only informs the teacher; the decision above stays deterministic.
        cls = self.tutor.classify(self, text) if (self.tutor and text) else None
        move = {"supported": "confirm", "insufficient_valid": "confirm", "misconception": "redirect"}.get(res.outcome, "probe")
        said = self._say(move, res.message, text)
        attempt = {"text": text, "cited": cited_ids, "hypothesis": self.hypothesis,
                   **res.student_view(), "message": said["text"], "source": said["source"],
                   "misconception": res.misconception, "classification": cls, "detail": res.teacher}
        self.attempts.append(attempt)
        self.feedback = {**res.student_view(), "message": said["text"]}
        self._log("reason.evaluated", **attempt)
        self._go("RECHECK" if res.passed else "EVIDENCE")
        return self.feedback

    def submit_exit(self, text: str):
        self._require("EXIT")
        if not text.strip():
            raise GuardError("empty answer")
        self.exit_answer = text.strip()[:300]
        self._log("exit.answered", text=self.exit_answer)
        self._go("CLOSED")

    def advance(self):
        """Move to the next state when its guard holds (technical design: state machine)."""
        s = self.state
        if s == "THEORY":
            self._require("THEORY")
            self._go("PREDICT")
        elif s == "PREDICT":
            self._require("PREDICT")
            if not self.prediction:
                raise GuardError("submit a prediction first")
            self._go("OBSERVE")
        elif s == "OBSERVE":
            self._require("OBSERVE")
            if self.visible_t() < self.ex["stop_s"]:
                raise GuardError("the recording has not reached the stop point")
            self._go("HYPOTHESIZE")
        elif s == "HYPOTHESIZE":
            self._require("HYPOTHESIZE")
            if not self.hypothesis:
                raise GuardError("choose a hypothesis first")
            self.feedback = None
            self._go("EVIDENCE")
        elif s == "EVIDENCE":
            self._require("EVIDENCE")
            if len(self.readings) < MIN_READINGS and self.hypothesis != "H-INSUFFICIENT":
                raise GuardError(f"save at least {MIN_READINGS} readings")
            self.feedback = None
            self._go("REASON")
        elif s == "RECHECK":
            self._require("RECHECK")
            if not any(r["t"] > self.ex["stop_s"] for r in self.readings):
                raise GuardError("save a reading after the stop point")
            self._go("EXIT")
        else:
            raise GuardError(f"cannot advance from {s}")

    # ---------- data ----------
    def _point(self, channel: str, t: int) -> dict:
        meta = content.channel_index()[channel]
        sample = self.recording.samples[t]
        value = sample.values[channel]
        quality = "ok"
        age = 0
        if meta.get("quality") and sample.flags.get(meta["quality"]) not in (None, "ok"):
            quality = sample.flags[meta["quality"]]
        if meta.get("source_time") and sample.flags.get(meta["source_time"]):
            from .ingest import _parse_time
            age = int((sample.timestamp - _parse_time(sample.flags[meta["source_time"]])).total_seconds())
        if value is None:
            quality = "missing"
        elif age > 1 and quality == "ok":
            quality = "stale"
        return {"value": value, "unit": meta["unit"], "quality": quality, "age_s": age,
                "name": meta["name"]}

    def _series(self, channel: str, upto: int) -> list[dict]:
        return [{"t": t, **{k: v for k, v in self._point(channel, t).items() if k in ("value", "quality", "age_s")}}
                for t in range(0, upto + 1)]

    def student_view(self) -> dict:
        ex, upto = self.ex, self.visible_t()
        idx = content.channel_index()
        cats = content.exercises()
        hyp_names = cats["hypotheses"]
        available = list(dict.fromkeys(ex["initial_channels"] + ex["openable_channels"]))
        groups = []
        for g in content.channels()["groups"]:
            items = [{"key": c["key"], "name": c["name"], "unit": c["unit"],
                      "open": c["key"] in self.open_channels}
                     for c in g["channels"] if c["key"] in available]
            if items:
                groups.append({"id": g["id"], "title": g["title"], "channels": items})
        mentor = {
            "THEORY": ex["goal"], "PREDICT": ex["predict"]["prompt"], "OBSERVE": ex["observe_prompt"],
            "RECHECK": ex["recheck_prompt"], "EXIT": ex["exit_question"],
        }.get(self.state, MENTOR_TEXT.get(self.state, ""))
        return {
            "id": self.id, "state": self.state, "state_rev": self.state_rev, "paused": self.paused,
            "step": STEP_OF[self.state], "steps": STEPS,
            # The student sees only the exercise number: names can give the answer away (teacher decision).
            "exercise": {"id": self.exercise_id, "number": exercise_number(self.exercise_id),
                         "goal": ex["goal"], "status": ex["status"], "stop_s": ex["stop_s"],
                         "duration": self.recording.duration, "windows": ex["windows"],
                         "cards": [{"id": k, **cats["knowledge_cards"][k]} for k in ex["cards"]],
                         "check": {"question": ex["check"]["question"], "choices": ex["check"]["choices"],
                                   "highlight_card": ex["check"]["highlight_card"]},
                         "predict_channels": [{"key": k, "name": idx[k]["name"]} for k in ex["predict"]["channels"]],
                         "hypotheses": [{"code": h, "label": hyp_names[h]} for h in ex["hypothesis_options"]]},
            "recording": {"alias": self.alias, "origin": self.recording.data_origin,
                          "runs": [{"from": i * 40, "label": f"הרצה {'אבגד'[i]}"}
                                   for i in range(len(self.recording.run_id.split("+")))]},
            "visible_t": upto,
            "groups": groups,
            "series": {k: {"name": idx[k]["name"], "unit": idx[k]["unit"], "points": self._series(k, upto)}
                       for k in self.open_channels} if upto >= 0 else {},
            "readings": self.readings,
            "hints": {"used": self.hints_used, "quota": self.hint_quota,
                      "given": self.hint_texts,
                      "sources": self.hint_sources},
            "note_from_teacher": self.teacher_message,
            "mentor_reply": self.mentor_reply,
            "can_ask": self.allow_ask and self.state in HINT_STATES,
            "label": self.label,
            "mentor": mentor,
            "feedback": self.feedback,
            "theory_answer": self.theory_answer,
            "prediction": self.prediction,
            "hypothesis": self.hypothesis,
            "exit_answer": self.exit_answer,
        }
