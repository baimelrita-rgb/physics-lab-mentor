"""Live station input (technical design · edge protocol, message obs.v1).

The edge agent sends one frame per second:
{"schema": "obs.v1", "station": "...", "seq": 184223, "t0": "2026-11-27T09:14:02.000Z", "dt_ms": 200,
 "ch": {"f_drive_hz": {"v": [49.8, 49.9, 50.0, 50.0, 50.1], "q": [0, 0, 0, 0, 0]}, ...}}
q: 0 = ok, 1 = stale, 2 = missing, 3 = out_of_range_sensor.
Channel keys are the station profile's channel keys (content/channels.yaml).
Frames are idempotent by (station, seq): a resend after a disconnect is ignored.
The station is read-only: there is no path from here back to the devices.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime

from . import content, envelope

Q = {0: "ok", 1: "stale", 2: "missing", 3: "out_of_range_sensor"}
KEEP_SECONDS = 600          # live history kept in memory per station
OFFLINE_AFTER = 5.0         # seconds without a frame or a heartbeat


class FrameError(ValueError):
    pass


@dataclass
class LiveSample:
    t: int
    at: str
    values: dict[str, float | None]
    quality: dict[str, str]


@dataclass
class LiveStation:
    station_id: str
    clock: callable = time.time
    samples: list[LiveSample] = field(default_factory=list)
    seen_seq: set = field(default_factory=set)
    last_seq: int | None = None
    gaps: int = 0
    duplicates: int = 0
    last_frame_at: float | None = None
    status: dict = field(default_factory=dict)
    status_at: float | None = None

    def ingest(self, frame: dict) -> bool:
        """Add one frame. Returns False for a duplicate (already received)."""
        if frame.get("schema") != "obs.v1":
            raise FrameError("schema must be obs.v1")
        if frame.get("station") != self.station_id:
            raise FrameError("station id does not match")
        seq = frame.get("seq")
        if not isinstance(seq, int) or seq < 0:
            raise FrameError("seq must be a non-negative integer")
        if seq in self.seen_seq:
            self.duplicates += 1
            return False
        try:
            datetime.fromisoformat(str(frame["t0"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            raise FrameError("t0 must be an ISO time")
        known = content.channel_index()
        values, quality = {}, {}
        for key, ch in (frame.get("ch") or {}).items():
            if key not in known:
                continue                       # unknown channels are ignored, never guessed
            vs, qs = ch.get("v", []), ch.get("q", [])
            if len(vs) != len(qs) or not vs:
                raise FrameError(f"{key}: v and q must have the same, non-zero length")
            good = [v for v, q in zip(vs, qs) if q in (0, 1) and isinstance(v, (int, float))]
            # One value per second: the mean of the usable points. All missing stays missing.
            values[key] = round(sum(good) / len(good), 4) if good else None
            worst = max(qs)
            quality[key] = Q.get(worst, "missing") if good or worst >= 2 else "missing"
        if self.last_seq is not None and seq > self.last_seq + 1:
            self.gaps += seq - self.last_seq - 1
        self.last_seq = seq if self.last_seq is None else max(self.last_seq, seq)
        self.seen_seq.add(seq)
        t = self.samples[-1].t + 1 if self.samples else 0
        self.samples.append(LiveSample(t, frame["t0"], values, quality))
        self.samples = self.samples[-KEEP_SECONDS:]
        self.last_frame_at = self.clock()
        return True

    def heartbeat(self, status: dict):
        self.status = {k: status.get(k) for k in ("agent_version", "clock_synced", "offline_buffer", "uptime_s")}
        self.status_at = self.clock()

    @property
    def connected(self) -> bool:
        last = max(x for x in (self.last_frame_at, self.status_at, 0) if x is not None)
        return self.clock() - last < OFFLINE_AFTER

    def monitor(self) -> dict:
        """Engineer view: latest value, quality and age per channel, plus the envelope state."""
        now = self.clock()
        latest = self.samples[-1] if self.samples else None
        rows = []
        for g in content.channels()["groups"]:
            for c in g["channels"]:
                k = c["key"]
                last_seen = next((smp for smp in reversed(self.samples) if smp.values.get(k) is not None), None)
                rows.append({
                    "key": k, "name": c["name"], "unit": c["unit"], "group": g["title"],
                    "value": latest.values.get(k) if latest else None,
                    "quality": (latest.quality.get(k, "not_sent") if latest else "not_sent"),
                    "last_value_t": last_seen.t if last_seen else None,
                })
        events = envelope.scan([(smp.t, smp.values) for smp in self.samples[-120:]])
        return {
            "station": self.station_id, "connected": self.connected, "samples": len(self.samples),
            "last_seq": self.last_seq, "gaps": self.gaps, "duplicates": self.duplicates,
            "seconds_since_frame": round(now - self.last_frame_at, 1) if self.last_frame_at else None,
            "agent": self.status, "channels": rows, "envelope": events,
            "rules": [{"id": r["id"], "title": r["title"], "status": r["status"],
                       "state": next((e["level"] for e in reversed(events) if e["rule"] == r["id"]), "ok")}
                      for r in envelope.rules()],
        }
