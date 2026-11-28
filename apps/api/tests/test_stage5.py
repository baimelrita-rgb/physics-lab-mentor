"""Stage 5: live station input (obs.v1) and the engineer monitor."""
import pytest
from fastapi.testclient import TestClient

from lab import app as appmod
from lab.live import FrameError, LiveStation

H = {"X-Device-Token": "dev-edge-token"}


def fr(seq, **ch):
    return {"schema": "obs.v1", "station": "st-t", "seq": seq, "t0": f"2026-11-28T09:00:{seq:02d}.000Z",
            "dt_ms": 200, "ch": {k: {"v": v, "q": q} for k, (v, q) in ch.items()}}


def test_mean_per_second_and_missing_stays_missing():
    st = LiveStation("st-t")
    st.ingest(fr(0, f_drive_hz=([49.8, 49.9, 50.0, 50.1, 50.2], [0] * 5),
                 i_v_rms_a=([None] * 5, [2] * 5), speed_rpm=([1467] * 5, [1] * 5)))
    s = st.samples[0]
    assert s.values["f_drive_hz"] == 50.0
    assert s.values["i_v_rms_a"] is None and s.quality["i_v_rms_a"] == "missing"
    assert s.quality["speed_rpm"] == "stale"


def test_duplicates_ignored_and_gaps_counted():
    st = LiveStation("st-t")
    assert st.ingest(fr(0, torque_nm=([0.65] * 5, [0] * 5)))
    assert not st.ingest(fr(0, torque_nm=([0.65] * 5, [0] * 5)))
    st.ingest(fr(3, torque_nm=([0.65] * 5, [0] * 5)))
    assert (st.duplicates, st.gaps, len(st.samples)) == (1, 2, 2)


def test_bad_frames_rejected():
    st = LiveStation("st-t")
    with pytest.raises(FrameError):
        st.ingest({**fr(0), "schema": "obs.v2"})
    with pytest.raises(FrameError):
        st.ingest(fr(1, torque_nm=([1, 2], [0])))
    with pytest.raises(FrameError):
        st.ingest({**fr(2), "station": "other"})


def test_unknown_channel_ignored():
    st = LiveStation("st-t")
    st.ingest(fr(0, made_up=([1] * 5, [0] * 5)))
    assert "made_up" not in st.samples[0].values


def test_envelope_on_live_overload():
    st = LiveStation("st-t")
    for i in range(4):
        st.ingest(fr(i, torque_nm=([2.85] * 5, [0] * 5)))
    rules = {r["id"]: r["state"] for r in st.monitor()["rules"]}
    assert rules["R-MOT-02"] == "stop" and rules["R-MOT-01"] == "ok"


def test_api_token_batch_and_monitor():
    c = TestClient(appmod.app)
    f = {**fr(0, f_drive_hz=([50.0] * 5, [0] * 5)), "station": "st-api"}
    assert c.post("/api/edge/stations/st-api/obs", json=f).status_code == 401
    batch = [{**f, "seq": i} for i in range(3)]
    r = c.post("/api/edge/stations/st-api/obs", json=batch, headers=H).json()
    assert r == {"accepted": 3, "last_seq": 2}
    assert c.post("/api/edge/stations/st-api/obs", json=batch, headers=H).json()["accepted"] == 0
    m = c.get("/api/teacher/stations/st-api/monitor").json()
    row = next(x for x in m["channels"] if x["key"] == "f_drive_hz")
    assert row["value"] == 50.0 and m["connected"] is True
    assert c.post("/api/edge/stations/st-api/obs", json={**f, "seq": 9, "schema": "x"}, headers=H).status_code == 422


def test_frequency_noise_around_50hz_is_not_a_violation():
    st = LiveStation("st-t")
    for i in range(6):
        st.ingest(fr(i, f_drive_hz=([49.9, 50.0, 50.1, 50.1, 50.0], [0] * 5)))
    assert {r["id"]: r["state"] for r in st.monitor()["rules"]}["R-MOT-03"] == "ok"
    for i in range(6, 10):
        st.ingest(fr(i, f_drive_hz=([55.0] * 5, [0] * 5)))
    assert {r["id"]: r["state"] for r in st.monitor()["rules"]}["R-MOT-03"] == "stop"
