"""Stage 8: class over time."""
from lab import classview, content
from lab.ingest import load_all, resolve
from lab.session import Session
from lab.teacher import Lesson


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def _lesson(cls, start, closed=True):
    l = Lesson("EX-01", clock=lambda: start, class_name=cls, date="2026-11-01")
    l.closed = closed
    return l


def _session(rec, l, label, start, hyp, sessions):
    c = Clock(start)
    s = Session("EX-01", rec, clock=c, label=label, lesson_id=l.id)
    s.advance(); s.submit_prediction({"speed_rpm": "down"}); c.t += 40; s.advance()
    c.t += 30; s.advance(); s.choose_hypothesis(hyp); s.advance()
    if hyp == "H-FREQ":
        ids = [s.add_reading("speed_rpm", 5)["id"], s.add_reading("speed_rpm", 20)["id"]]
        s.advance(); c.t += 10; s.submit_reason("התדר ירד", ids)
        c.t += 1000                                   # long time in evidence after the redirect
        s.request_hint()
    l.session_ids.append(s.id)
    sessions[s.id] = s
    return s


def test_class_view_aggregates():
    rec = resolve(load_all(content.DATA), "E03")
    sessions = {}
    a, b = _lesson("י׳1", 1_000_000), _lesson("י׳1", 2_000_000)
    other = _lesson("י׳3", 1_500_000)
    _session(rec, a, "קבוצה א", 1_000_000, "H-FREQ", sessions)
    _session(rec, a, "קבוצה ב", 1_000_000, "H-LOAD", sessions)
    _session(rec, b, "קבוצה א", 2_000_000, "H-LOAD", sessions)
    _session(rec, other, "קבוצה א", 1_500_000, "H-FREQ", sessions)
    d = classview.build([a, b, other], sessions, "י׳1", None, now=3_000_000)
    assert [l["id"] for l in d["lessons"]] == [a.id, b.id]
    assert {h["label"] for h in d["heatmap"]} == {"קבוצה א", "קבוצה ב"}
    m01 = next(m for m in d["misconceptions"] if m["id"] == "M-01")
    assert m01["groups"] == 1 and [t["share"] for t in m01["trend"]] == [0.5, 0.0] and m01["direction"] == "down"
    ev = next(s for s in d["stages"] if s["state"] == "EVIDENCE")
    assert ev["stuck"] == 1 and ev["hints"] == 1
    # closed lesson: aspects never reached count as 0, and time stops at the last action
    assert all(x is not None for h in d["heatmap"] for x in h["aspects"])
    assert ev["max_s"] < 2000
    # period filter
    assert len(classview.build([a, b], sessions, "י׳1", 7, now=2_000_000 + 86400)["lessons"]) == 1


def test_class_names_and_planned_excluded():
    l1, l2 = _lesson("י׳1", 0), _lesson("", 0)
    planned = _lesson("י׳1", 0); planned.planned = True
    names = classview.class_names([l1, l2])
    assert names == [{"name": "י׳1", "lessons": 1}, {"name": classview.NO_CLASS, "lessons": 1}]
    assert classview.build([planned], {}, "י׳1", None)["lessons"] == []
