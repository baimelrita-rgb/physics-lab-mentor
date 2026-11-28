"""Edge agent simulator: behaves like the UNO Q agent and streams a recorded run as live obs.v1 frames.

- One frame per second, 5 points per channel (5 Hz), with the quality flags of the recording.
- Frames that cannot be sent stay in a local buffer and are flushed, in order, when the
  server is back (the real agent keeps 24 h in SQLite). The server ignores duplicates.
- A heartbeat every 10 frames.
- Read-only: it only sends measurements. Standard library only.

Run from the repository root while the server runs:
    python3 tools/simulator/station_agent.py --run E04 --speed 2
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANNELS = ["grid_v_rms_v", "grid_i_rms_a", "grid_pf", "grid_p_active_w", "grid_f_hz", "f_set_hz", "f_drive_hz",
            "u_uv_fund_rms_v", "u_vw_fund_rms_v", "u_wu_fund_rms_v", "i_u_rms_a", "i_v_rms_a", "i_w_rms_a",
            "speed_rpm", "torque_nm", "motor_temp_c", "vibration_rms_mm_s"]
QUALITY = {"i_v_rms_a": "i_v_quality", "speed_rpm": "speed_quality"}
Q = {"ok": 0, "stale": 1, "missing": 2}


def load_run(run: str) -> list[dict]:
    for p in sorted((ROOT / "data").glob("*.csv")):
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["run_id"] == run]
        if rows:
            return sorted(rows, key=lambda r: int(r["sample_index"]))
    raise SystemExit(f"run {run} not found in data/")


def frame(station: str, seq: int, t0: datetime, row: dict, rng: random.Random) -> dict:
    ch = {}
    for k in CHANNELS:
        raw = row[k]
        flag = row.get(QUALITY.get(k, ""), "") or ("missing" if raw == "" else "ok")
        q = Q.get(flag, 2)
        if raw == "":
            ch[k] = {"v": [None] * 5, "q": [2] * 5}
            continue
        base = float(raw)
        # Small sensor noise around the recorded 1 s value; a stale value is repeated as-is.
        jitter = 0 if q == 1 else abs(base) * 0.0005
        ch[k] = {"v": [round(base + rng.uniform(-jitter, jitter), 4) for _ in range(5)], "q": [q] * 5}
    return {"schema": "obs.v1", "station": station, "seq": seq,
            "t0": t0.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "dt_ms": 200, "ch": ch}


def post(url: str, token: str, body) -> bool:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Device-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        print(f"server refused: {e.code} {e.read()[:200]!r}")
        return e.code == 422            # a bad frame is dropped, not retried forever
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="N03_LOAD_STEP", help="run id to replay (e.g. E04, N02_50HZ)")
    ap.add_argument("--station", default="st-1")
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--token", default="dev-edge-token")
    ap.add_argument("--speed", type=float, default=1.0, help="frames per second (1 = real time)")
    ap.add_argument("--loop", action="store_true", help="start the run again at the end")
    ap.add_argument("--count", type=int, default=0, help="stop after N frames (0 = whole run)")
    a = ap.parse_args()

    rows, rng = load_run(a.run), random.Random(7)
    obs_url = f"{a.url}/api/edge/stations/{a.station}/obs"
    status_url = f"{a.url}/api/edge/stations/{a.station}/status"
    buffer: deque = deque(maxlen=24 * 3600)
    t0, seq, start = datetime.now(timezone.utc), 0, time.monotonic()
    while True:
        for row in rows:
            buffer.append(frame(a.station, seq, t0 + timedelta(seconds=seq), row, rng))
            if post(obs_url, a.token, list(buffer)):
                buffer.clear()
            else:
                print(f"server unreachable, {len(buffer)} frame(s) buffered")
            if seq % 10 == 0:
                post(status_url, a.token, {"agent_version": "sim-0.1", "clock_synced": True,
                                           "offline_buffer": len(buffer), "uptime_s": int(time.monotonic() - start)})
            seq += 1
            if a.count and seq >= a.count:
                return
            time.sleep(1 / a.speed)
        if not a.loop:
            return


if __name__ == "__main__":
    main()
