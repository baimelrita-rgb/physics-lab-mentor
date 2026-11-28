import json

import pytest

from lab import content
from lab.ingest import SchemaError, load_all, load_csv, resolve
from lab.session import GuardError, Session

CSV = content.DATA / "TLM_Rita_Labeled_Errors.csv"


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def recs():
    return load_all(content.DATA)


def new(recs, ex="EX-01"):
    clock = Clock()
    rec = content.exercises()["exercises"][ex]["recording"]
    return Session(ex, resolve(recs, rec), clock=clock), clock


# ---------- import ----------
def test_import_schema_and_counts():
    ds = load_csv(CSV)
    assert set(ds.recordings) == {"E01", "E02", "E03", "E04"}
    assert all(len(r.samples) == 40 for r in ds.recordings.values())
    assert len(ds.sha256) == 64


def test_empty_cell_is_none_not_zero(recs):
    s = recs["E01"].samples[15]
    assert s.values["i_v_rms_a"] is None
    assert s.flags["i_v_quality"] == "missing"


def test_rejects_other_schema(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_bytes(b"\xef\xbb\xbfa,b\n1,2\n")
    with pytest.raises(SchemaError):
        load_csv(p)


def test_rejects_missing_bom(tmp_path):
    p = tmp_path / "nobom.csv"
    p.write_bytes(CSV.read_bytes()[3:])
    with pytest.raises(SchemaError):
        load_csv(p)


# ---------- time gate ----------
def test_nothing_visible_before_observe_and_stop_at_22(recs):
    s, clock = new(recs)
    assert s.visible_t() == -1
    s.advance()
    s.submit_prediction({"speed_rpm": "down"})
    s.advance()
    clock.t = 5
    assert s.visible_t() == 5
    with pytest.raises(GuardError):
        s.advance()                       # recording not at the stop point yet
    clock.t = 100
    assert s.visible_t() == 22            # never past the stop point while observing
    s.advance()
    assert s.state == "HYPOTHESIZE"


def test_cannot_read_future_second(recs):
    s, clock = _to_evidence(recs)
    with pytest.raises(GuardError):
        s.add_reading("speed_rpm", 30)


# ---------- answer wall ----------
def test_student_view_has_no_teacher_data(recs):
    s, clock = _to_evidence(recs)
    s.open_channel("f_drive_hz")
    blob = json.dumps(s.student_view(), ensure_ascii=False)
    for word in ("teacher_", "planned_load", "E03","H-LOAD\": \"cause", "תוספת עומס", "answer_key", "check_answer"):
        assert word not in blob


def test_closed_channel_data_not_sent(recs):
    s, clock = _to_evidence(recs)
    assert set(s.student_view()["series"]) == {"speed_rpm"}


# ---------- diagnosis ----------
def _to_evidence(recs, hyp="H-LOAD"):
    s, clock = new(recs)
    s.advance()
    s.submit_prediction({"speed_rpm": "down", "f_drive_hz": "same"})
    s.advance()
    clock.t = 30
    s.advance()
    s.choose_hypothesis(hyp)
    s.advance()
    return s, clock


def test_ex01_supported_path_to_closed(recs):
    s, clock = _to_evidence(recs)
    s.open_channel("f_drive_hz", "same")
    s.open_channel("torque_nm", "up")
    ids = [s.add_reading("f_drive_hz", 5)["id"], s.add_reading("f_drive_hz", 20)["id"],
           s.add_reading("torque_nm", 20)["id"]]
    s.advance()
    fb = s.submit_reason("התדר נשאר 50 והמומנט עלה", ids)
    assert fb["outcome"] == "supported" and s.state == "RECHECK"
    with pytest.raises(GuardError):
        s.advance()                       # needs a reading after the stop point
    clock.t = 40
    s.add_reading("torque_nm", 30)
    s.advance()
    s.submit_exit("כן, ההחלקה גדלה כשהעומס עולה")
    assert s.state == "CLOSED"


def test_ex01_frequency_hypothesis_gets_redirect_and_loops(recs):
    s, clock = _to_evidence(recs, "H-FREQ")
    ids = [s.add_reading("speed_rpm", 5)["id"], s.add_reading("speed_rpm", 20)["id"]]
    s.advance()
    fb = s.submit_reason("המהירות ירדה כי התדר ירד", ids)
    assert fb["outcome"] == "misconception" and not fb["passed"]
    assert s.state == "EVIDENCE"
    assert "H-LOAD" not in json.dumps(fb)


def test_ex01_right_cause_without_frequency_evidence_is_unsupported(recs):
    s, clock = _to_evidence(recs)
    s.open_channel("torque_nm")
    ids = [s.add_reading("torque_nm", 5)["id"], s.add_reading("torque_nm", 20)["id"]]
    s.advance()
    assert s.submit_reason("המומנט עלה", ids)["outcome"] == "unsupported"


def test_hint_quota(recs):
    s, clock = _to_evidence(recs)
    assert [s.request_hint() for _ in range(3)][0].startswith("האם מהירות")
    with pytest.raises(GuardError):
        s.request_hint()


def test_ex03_stale_reading_flagged(recs):
    s, clock = new(recs, "EX-03")
    s.advance(); s.submit_prediction({"speed_rpm": "up"}); s.advance()
    clock.t = 30; s.advance(); s.choose_hypothesis("H-LOAD"); s.advance()
    r = s.add_reading("speed_rpm", 18)
    assert r["quality"] == "stale" and r["age_s"] == 9


def test_theory_check(recs):
    s, clock = new(recs)
    assert s.answer_theory(0) is True
    assert s.answer_theory(2) is False
