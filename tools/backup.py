"""Consistent backup of all server state while the server runs.

    python3 tools/backup.py                      # -> var/backups/lab-YYYYmmdd-HHMMSS.tar.gz
    python3 tools/backup.py /mnt/backups --keep 14

One archive holds a consistent copy of the database (SQLite online backup) plus the other state
files: teacher accounts, class rosters, station token hashes, per-tenant content edits and the
cookie signing key. Restore: stop the server, unpack the archive into the state folder, start.
In the cloud deployment (deploy/) the backup service runs this every night; copy the folder off
the server (or mount object storage there).
"""
import argparse
import os
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.store import Store  # noqa: E402

STATE_FILES = ("teachers.json", "rosters.json", "stations.json", "secret.key", "content_overrides*.json")


def backup(state: Path, target: Path, keep: int) -> Path:
    target.mkdir(parents=True, exist_ok=True)
    out = target / f"lab-{time.strftime('%Y%m%d-%H%M%S')}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "lab.db"
        Store(state).backup(db)
        part = out.with_suffix(".part")
        with tarfile.open(part, "w:gz") as tar:
            tar.add(db, arcname="lab.db")
            for pattern in STATE_FILES:
                for f in sorted(state.glob(pattern)):
                    tar.add(f, arcname=f.name)
        os.chmod(part, 0o600)
        os.replace(part, out)
    for old in sorted(target.glob("lab-*.tar.gz"))[:-keep]:
        old.unlink()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default=str(ROOT / "var" / "backups"))
    ap.add_argument("--keep", type=int, default=14, help="how many backups to keep")
    ap.add_argument("--every", type=float, default=0, help="hours between backups; 0 = once and exit")
    a = ap.parse_args()
    state = Path(os.environ.get("STATE_DIR", ROOT / "var" / "state"))
    while True:
        print(backup(state, Path(a.target), a.keep), flush=True)
        if not a.every:
            break
        time.sleep(a.every * 3600)


if __name__ == "__main__":
    main()
