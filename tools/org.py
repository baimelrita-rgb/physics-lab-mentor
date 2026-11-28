"""Manage tenants (schools / networks), labs and stations (MVP package 4).

Run from the repository root (stop the server first, or run it on the same host: SQLite is shared):
    python3 tools/org.py list
    python3 tools/org.py add-tenant school-a "תיכון א"
    python3 tools/org.py add-lab lab-a1 school-a "מעבדת פיזיקה 1"
    python3 tools/org.py assign-station ST-MOT-VFD-1 lab-a1 "עמדה 1"
Teachers get a tenant with:  python3 tools/add_teacher.py <user> "<name>" --tenant school-a
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.org import Org, OrgError  # noqa: E402
from lab.store import Store  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    store = Store(Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")))
    org = Org(store.db, store._lock)
    cmd, args = sys.argv[1], sys.argv[2:]
    try:
        if cmd == "list":
            for t in org.tenants():
                print(f"{t['id']}  {t['name']}")
                for lab in org.labs(t["id"]):
                    print(f"   {lab['id']}  {lab['name']}")
                    for (sid, name) in store.db.execute("SELECT station_id, name FROM station_labs WHERE lab_id = ?", (lab["id"],)):
                        print(f"      {sid}  {name}")
        elif cmd == "add-tenant" and len(args) >= 1:
            org.add_tenant(args[0], args[1] if len(args) > 1 else args[0])
        elif cmd == "add-lab" and len(args) >= 2:
            org.add_lab(args[0], args[1], args[2] if len(args) > 2 else args[0])
        elif cmd == "assign-station" and len(args) >= 2:
            org.assign_station(args[0], args[1], args[2] if len(args) > 2 else "")
        else:
            sys.exit(__doc__)
    except OrgError as e:
        sys.exit(str(e))
    if cmd != "list":
        print("נשמר.")


if __name__ == "__main__":
    main()
