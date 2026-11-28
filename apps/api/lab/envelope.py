"""Safety envelope checker: runs the limit rules over measurements (Brain 1 · limits guide).

The station's own hardware protections are Talem's and independent of this system:
this checker only raises alerts. A missing value never counts as within or outside a limit.
"""
from __future__ import annotations

from functools import lru_cache

import yaml

from . import content


@lru_cache
def rules() -> list[dict]:
    return yaml.safe_load((content.CONTENT / "envelope.yaml").read_text(encoding="utf-8"))["rules"]


def _level(rule: dict, value: float) -> str | None:
    lo, hi = rule.get("min"), rule.get("max")
    if rule.get("active_above") is not None and value <= rule["active_above"]:
        return None
    tol = rule.get("tolerance", 0)
    if (hi is not None and value > hi + tol) or (lo is not None and value < lo - tol):
        return "stop"
    if hi is not None and rule.get("warn_ratio") and value >= hi * rule["warn_ratio"]:
        return "warn"
    return None


def scan(values_by_t: list[tuple[int, dict]]) -> list[dict]:
    """Check a time series [(t, {channel: value|None})] in order.

    Returns one event per rule and level, at the first second the condition has held for hold_s:
    {rule, title, level, t, channel, value, limit, status}.
    """
    events = []
    for rule in rules():
        for level in ("warn", "stop"):
            run_start, hit = None, None
            for t, vals in values_by_t:
                worst = None
                for ch in rule["channels"]:
                    v = vals.get(ch)
                    if v is None:
                        continue
                    lv = _level(rule, v)
                    if lv == "stop" or (lv == "warn" and level == "warn"):
                        worst = (ch, v)
                        break
                if worst:
                    run_start = t if run_start is None else run_start
                    if t - run_start + 1 >= rule.get("hold_s", 1):
                        hit = (t, *worst)
                        break
                else:
                    run_start = None
            if hit:
                t, ch, v = hit
                hi = rule.get("max")
                limit = hi if hi is not None and v >= hi * (rule.get("warn_ratio") or 1) else rule.get("min")
                events.append({"rule": rule["id"], "title": rule["title"], "level": level, "t": t,
                               "channel": ch, "value": v, "limit": limit, "status": rule["status"]})
    # A "warning" whose value is already past the limit is the stop itself: keep only the stop.
    by_id = {r["id"]: r for r in rules()}
    stopped = {e["rule"] for e in events if e["level"] == "stop"}
    events = [e for e in events
              if not (e["level"] == "warn" and e["rule"] in stopped and _level(by_id[e["rule"]], e["value"]) == "stop")]
    return sorted(events, key=lambda e: (e["t"], e["level"] != "stop"))


_cache: dict[str, list[dict]] = {}


def for_recording(recording) -> list[dict]:
    """Envelope events of a whole recording (recordings never change, so this is cached)."""
    if recording.run_id not in _cache:
        _cache[recording.run_id] = scan([(smp.t, smp.values) for smp in recording.samples])
    return _cache[recording.run_id]
