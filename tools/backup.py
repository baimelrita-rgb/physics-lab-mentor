"""Consistent backup of the lab database while the server runs.

    python3 tools/backup.py                      # -> var/backups/lab-YYYYmmdd-HHMMSS.db
    python3 tools/backup.py /mnt/backups --keep 14

Run it daily (cron or the cloud scheduler) and copy the folder off the server.
"""
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.store import Store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default=str(ROOT / "var" / "backups"))
    ap.add_argument("--keep", type=int, default=14, help="how many backups to keep")
    a = ap.parse_args()
    store = Store(Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")))
    target = Path(a.target)
    out = target / f"lab-{time.strftime('%Y%m%d-%H%M%S')}.db"
    store.backup(out)
    for old in sorted(target.glob("lab-*.db"))[:-a.keep]:
        old.unlink()
    print(out)


if __name__ == "__main__":
    main()
