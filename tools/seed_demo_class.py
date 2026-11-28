"""Create a demo class with four past lessons, so the "class" tab has something to show.

Run from the repository root (the server must be restarted afterwards to load them):
    python3 tools/seed_demo_class.py                 # visible in demo mode / to every teacher
    python3 tools/seed_demo_class.py --owner rita    # only for this teacher
Sessions are driven through the real state machine with a simulated clock, so durations,
hints, misconceptions and suggested scores are computed exactly as in a real lesson.
All data is invented and the class is named "(הדגמה)". Remove it with --remove.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab import content  # noqa: E402
from lab.ingest import load_all, resolve  # noqa: E402
from lab.session import Session  # noqa: E402
from lab.store import Store  # noqa: E402
from lab.teacher import Lesson  # noqa: E402

CLASS = "י׳2 (הדגמה)"
GROUPS = ["קבוצה א", "קבוצה ב", "קבוצה ג", "קבוצה ד", "קבוצה ה"]


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def to_evidence(s, c, hyp, think=60):
    s.answer_theory(content.answer_key()[s.exercise_id]["check_answer"]); c.t += 90; s.advance()
    s.submit_prediction({"speed_rpm": "down", "f_drive_hz": "same"}); c.t += 60; s.advance()
    c.t += 30; s.advance()
    c.t += think; s.choose_hypothesis(hyp); c.t += 20; s.advance()


def strong(s, c, extra=0):
    to_evidence(s, c, "H-LOAD")
    s.open_channel("f_drive_hz", "same"); s.open_channel("torque_nm", "up")
    ids = [s.add_reading("f_drive_hz", 5)["id"], s.add_reading("f_drive_hz", 20)["id"], s.add_reading("torque_nm", 20)["id"]]
    c.t += 150 + extra; s.advance()
    c.t += 120; s.submit_reason("התדר נשאר 50 והמומנט עלה, לכן ההאטה מהעומס", ids)
    c.t += 40; s.add_reading("torque_nm", 30); c.t += 60; s.advance()
    c.t += 90; s.submit_exit("כן. כשהעומס גדל ההחלקה גדלה והמהירות יורדת גם בתדר קבוע.")


def needs_hints(s, c):
    to_evidence(s, c, "H-LOAD", think=150)
    c.t += 200; s.request_hint()
    c.t += 160; s.request_hint()
    s.open_channel("torque_nm")                      # opened only after two hints
    s.open_channel("f_drive_hz")
    ids = [s.add_reading("f_drive_hz", 5)["id"], s.add_reading("f_drive_hz", 20)["id"], s.add_reading("torque_nm", 20)["id"]]
    c.t += 120; s.advance()
    c.t += 150; s.submit_reason("המומנט עלה והתדר לא השתנה", ids)
    c.t += 60; s.add_reading("torque_nm", 32); c.t += 30; s.advance()
    c.t += 120; s.submit_exit("כן, בגלל ההחלקה")


def freq_misconception(s, c):
    to_evidence(s, c, "H-FREQ")
    ids = [s.add_reading("speed_rpm", 5)["id"], s.add_reading("speed_rpm", 20)["id"]]
    c.t += 120; s.advance()
    c.t += 100; s.submit_reason("המהירות ירדה כי התדר ירד", ids)
    c.t += 380; s.request_hint()                     # stuck in evidence after the redirect
    s.open_channel("f_drive_hz", "down")
    c.t += 200


def stuck_evidence(s, c):
    to_evidence(s, c, "H-LOAD", think=240)
    c.t += 420; s.request_hint()
    s.open_channel("torque_nm"); c.t += 180


PLANS = [  # one entry per lesson: (days ago, profile per group). Later lessons improve.
    (27, [strong, freq_misconception, freq_misconception, stuck_evidence, needs_hints]),
    (20, [strong, freq_misconception, needs_hints, stuck_evidence, needs_hints]),
    (13, [strong, needs_hints, freq_misconception, needs_hints, strong]),
    (6, [strong, strong, needs_hints, needs_hints, strong]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="")
    ap.add_argument("--remove", action="store_true")
    a = ap.parse_args()
    state = Path(os.environ.get("STATE_DIR", ROOT / "var" / "state"))
    store = Store(state)
    lessons_dir = state / "lessons"
    # Remove an earlier demo class first, so running twice does not duplicate it.
    for p in sorted(lessons_dir.glob("*.json")) if lessons_dir.exists() else []:
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("class_name") == CLASS:
            for sid in d.get("session_ids", []):
                (state / "sessions" / f"{sid}.json").unlink(missing_ok=True)
            p.unlink()
    if a.remove:
        print("הכיתה לדוגמה נמחקה. הפעילו מחדש את השרת.")
        return
    recs = load_all(content.DATA)
    rec = resolve(recs, content.exercises()["exercises"]["EX-01"]["recording"])
    now = time.time()
    for days_ago, profiles in PLANS:
        start = now - days_ago * 86400
        lesson = Lesson("EX-01", clock=lambda: start, owner=a.owner, class_name=CLASS,
                        date=time.strftime("%Y-%m-%d", time.localtime(start)), stations=len(GROUPS))
        lesson.clock = time.time
        lesson.closed = True
        for group, run in zip(GROUPS, profiles):
            c = Clock(start)
            s = Session("EX-01", rec, clock=c, label=group, lesson_id=lesson.id)
            run(s, c)
            s.clock = time.time
            lesson.session_ids.append(s.id)
            store.save_session(s)
        store.save_lesson(lesson)
    print(f"נוצרה כיתה לדוגמה: {CLASS}, {len(PLANS)} שיעורים, {len(GROUPS)} קבוצות. הפעילו מחדש את השרת.")


if __name__ == "__main__":
    main()
