"""Build the healthy reference runs N01_25HZ, N02_50HZ and N03_LOAD_STEP.

The original "Normal" CSV was not available, so this rebuilds it from the
specification in source-docs/TLM_Rita_02_Healthy.docx and Brain 3:
- N01_25HZ: steady 25 Hz. Built from the steady part of E02 (seconds 0-9).
- N02_50HZ: steady 50 Hz. Built from the steady part of E03 (seconds 0-11).
- N03_LOAD_STEP: E03 without the simulated student hypothesis at second 22
  (Brain 3: "E03 is identical to N03, with a simulated student hypothesis at 22").
Steady runs repeat the measured noise pattern of their source rows; motor case
temperature keeps rising slowly. Every checkpoint from the spec is asserted below.

Run from the repository root:  python3 tools/simulator/make_healthy.py
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "TLM_Rita_Labeled_Errors.csv"
OUT = ROOT / "data" / "TLM_Rita_Normal_SIMULATED.csv"
N = 40
START = {"N01_25HZ": "2026-11-27T08:00:00Z", "N02_50HZ": "2026-11-27T08:02:00Z",
         "N03_LOAD_STEP": "2026-11-27T08:04:00Z"}
HEALTHY = {"teacher_domain": "normal", "teacher_event_id": "", "teacher_label": "healthy_reference",
           "teacher_student_assessment": "", "teacher_plant_state": "steady_reference",
           "teacher_data_state": "valid", "teacher_learner_state": "no_response_recorded"}

# Checkpoints copied from the spec tables: run, second, column -> value.
CHECKS = [
    ("N01_25HZ", 0, {"f_drive_hz": "25.0", "i_u_rms_a": "0.729", "i_v_rms_a": "0.727", "i_w_rms_a": "0.733",
                     "speed_rpm": "717", "torque_nm": "0.65", "grid_p_active_w": "141.0", "grid_f_hz": "50.0",
                     "u_uv_fund_rms_v": "189.6", "u_vw_fund_rms_v": "189.9", "u_wu_fund_rms_v": "189.5"}),
    ("N02_50HZ", 0, {"f_drive_hz": "50.0", "i_u_rms_a": "0.729", "i_v_rms_a": "0.727", "i_w_rms_a": "0.733",
                     "speed_rpm": "1467", "torque_nm": "0.65", "grid_p_active_w": "205.1",
                     "u_uv_fund_rms_v": "379.2", "u_vw_fund_rms_v": "379.7", "u_wu_fund_rms_v": "379.0"}),
    ("N03_LOAD_STEP", 5, {"f_drive_hz": "50.0", "i_u_rms_a": "0.728", "i_v_rms_a": "0.724", "i_w_rms_a": "0.731",
                          "speed_rpm": "1467", "torque_nm": "0.65", "grid_p_active_w": "205.2",
                          "u_uv_fund_rms_v": "379.3", "u_vw_fund_rms_v": "379.6", "u_wu_fund_rms_v": "378.7"}),
    ("N03_LOAD_STEP", 12, {"f_drive_hz": "50.0", "i_u_rms_a": "0.771", "i_v_rms_a": "0.767", "i_w_rms_a": "0.772",
                           "speed_rpm": "1461", "torque_nm": "0.83", "grid_p_active_w": "238.8",
                           "u_uv_fund_rms_v": "379.1", "u_vw_fund_rms_v": "379.6", "u_wu_fund_rms_v": "379.0"}),
    ("N03_LOAD_STEP", 22, {"f_drive_hz": "50.0", "i_u_rms_a": "0.935", "i_v_rms_a": "0.930", "i_w_rms_a": "0.937",
                           "speed_rpm": "1423", "torque_nm": "1.55", "grid_p_active_w": "371.9",
                           "u_uv_fund_rms_v": "379.2", "u_vw_fund_rms_v": "379.5", "u_wu_fund_rms_v": "378.8"}),
]


def ts(start: str, t: int) -> str:
    base = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return (base + timedelta(seconds=t)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def steady(run_id: str, source: list[dict]) -> list[dict]:
    rows = []
    for t in range(N):
        r = dict(source[t % len(source)])
        r.update(HEALTHY, run_id=run_id, sample_index=str(t), student_hypothesis="",
                 timestamp_utc=ts(START[run_id], t))
        r["speed_sample_utc"] = r["timestamp_utc"]
        r["motor_temp_c"] = f"{float(source[0]['motor_temp_c']) + 0.002 * t:.2f}"
        rows.append(r)
    return rows


def load_step(source: list[dict]) -> list[dict]:
    rows = []
    for r0 in source:
        r = dict(r0)
        t = int(r["sample_index"])
        r.update(run_id="N03_LOAD_STEP", student_hypothesis="", timestamp_utc=ts(START["N03_LOAD_STEP"], t))
        r["speed_sample_utc"] = r["timestamp_utc"]
        if r["teacher_event_id"].startswith("E03"):
            # The simulated learner error at 22 is not part of the healthy run.
            r.update(teacher_domain="process_expected", teacher_event_id="N03_LOAD_STEP-L",
                     teacher_label="planned_load_increase", teacher_student_assessment="",
                     teacher_plant_state="planned_load", teacher_data_state="valid",
                     teacher_learner_state="no_response_recorded")
        rows.append(r)
    return rows


def main():
    with SRC.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        src = list(reader)
    by = lambda run: sorted((r for r in src if r["run_id"] == run), key=lambda r: int(r["sample_index"]))
    e02, e03 = by("E02"), by("E03")
    out = (steady("N01_25HZ", e02[:10]) + steady("N02_50HZ", e03[:12]) + load_step(e03))

    index = {(r["run_id"], int(r["sample_index"])): r for r in out}
    for run, t, expected in CHECKS:
        for col, val in expected.items():
            got = index[(run, t)][col]
            assert got == val, f"{run} s{t} {col}: {got} != {val}"
    assert len(out) == 120

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\r\n")
    w.writeheader()
    w.writerows(out)
    OUT.write_bytes(b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8"))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} rows, all {sum(len(c[2]) for c in CHECKS)} checkpoints match")


if __name__ == "__main__":
    main()
