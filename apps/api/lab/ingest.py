"""Import synthetic recordings (Brain 3 · import rules).

- UTF-8 with BOM and exactly the 33 known fields; any other schema is rejected.
- An empty cell is kept as None. Missing values are never filled or interpolated.
- speed_sample_utc is kept as-is; the age of a reading is computed at read time.
- teacher_* columns go to the answer key side; student_hypothesis to the test set.
- The source file is kept unchanged and identified by its sha256.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

FIELDS = [
    "station_id", "data_origin", "timestamp_utc", "run_id", "sample_index",
    "grid_v_rms_v", "grid_i_rms_a", "grid_pf", "grid_p_active_w", "grid_f_hz",
    "f_set_hz", "f_drive_hz", "u_uv_fund_rms_v", "u_vw_fund_rms_v", "u_wu_fund_rms_v",
    "i_u_rms_a", "i_v_rms_a", "i_w_rms_a", "i_v_quality", "speed_rpm",
    "speed_sample_utc", "speed_quality", "torque_nm", "motor_temp_c", "vibration_rms_mm_s",
    "student_hypothesis", "teacher_domain", "teacher_event_id", "teacher_label",
    "teacher_student_assessment", "teacher_plant_state", "teacher_data_state",
    "teacher_learner_state",
]
NUMERIC = {
    "grid_v_rms_v", "grid_i_rms_a", "grid_pf", "grid_p_active_w", "grid_f_hz",
    "f_set_hz", "f_drive_hz", "u_uv_fund_rms_v", "u_vw_fund_rms_v", "u_wu_fund_rms_v",
    "i_u_rms_a", "i_v_rms_a", "i_w_rms_a", "speed_rpm", "torque_nm", "motor_temp_c",
    "vibration_rms_mm_s",
}
TEXT_SIGNAL = {"i_v_quality", "speed_quality", "speed_sample_utc"}
TEACHER = [f for f in FIELDS if f.startswith("teacher_")]


class SchemaError(ValueError):
    pass


@dataclass
class Sample:
    t: int                      # seconds from run start (sample_index, 1 s spacing)
    timestamp: datetime
    values: dict[str, float | None]
    flags: dict[str, str | None]


@dataclass
class Recording:
    run_id: str
    station_id: str
    data_origin: str
    samples: list[Sample]
    # Behind the wall: never exposed through the student API.
    teacher_rows: list[dict[str, str | None]] = field(repr=False)
    student_hypotheses: list[tuple[int, str]] = field(repr=False)

    @property
    def duration(self) -> int:
        return self.samples[-1].t


@dataclass
class Dataset:
    source: str
    sha256: str
    recordings: dict[str, Recording]


def _parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load_csv(path: str | Path) -> Dataset:
    raw = Path(path).read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf"):
        raise SchemaError(f"{path}: expected UTF-8 with BOM")
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames != FIELDS:
        raise SchemaError(f"{path}: unexpected schema {reader.fieldnames}")

    by_run: dict[str, list[dict[str, str]]] = {}
    for row in reader:
        by_run.setdefault(row["run_id"], []).append(row)

    recordings = {}
    for run_id, rows in by_run.items():
        rows.sort(key=lambda r: int(r["sample_index"]))
        samples, teacher, hyps = [], [], []
        for r in rows:
            t = int(r["sample_index"])
            values = {k: (float(r[k]) if r[k] != "" else None) for k in NUMERIC}
            flags = {k: (r[k] or None) for k in TEXT_SIGNAL}
            samples.append(Sample(t, _parse_time(r["timestamp_utc"]), values, flags))
            teacher.append({"t": t, **{k: (r[k] or None) for k in TEACHER}})
            if r["student_hypothesis"]:
                hyps.append((t, r["student_hypothesis"]))
        first = rows[0]
        recordings[run_id] = Recording(
            run_id, first["station_id"], first["data_origin"], samples, teacher, hyps
        )
    return Dataset(str(path), hashlib.sha256(raw).hexdigest(), recordings)


def load_all(data_dir: str | Path) -> dict[str, Recording]:
    out: dict[str, Recording] = {}
    for p in sorted(Path(data_dir).glob("*.csv")):
        out.update(load_csv(p).recordings)
    return out
