"""Add a teacher account (or reset its password).

Run from the repository root:
    python3 tools/add_teacher.py rita "ריטה" [--tenant school-a] [--role content_admin] [--labs lab-1,lab-2]
The password is asked twice and never shown. It is stored only as a salted PBKDF2 hash in
var/state/teachers.json (or $STATE_DIR/teachers.json). Once one account exists, the teacher
screens require login (demo mode ends).
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.auth import Auth, AuthError  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("username")
    ap.add_argument("name", nargs="?")
    ap.add_argument("--tenant", default="default", help="school / network id (see tools/org.py)")
    ap.add_argument("--role", default="teacher", choices=["teacher", "content_admin"])
    ap.add_argument("--labs", default="", help="comma-separated lab ids this teacher sees (empty = all labs of the tenant)")
    a = ap.parse_args()
    username, name = a.username, a.name or a.username
    pw = getpass.getpass("סיסמה (8 תווים לפחות): ")
    if pw != getpass.getpass("שוב: "):
        sys.exit("הסיסמאות לא זהות.")
    auth = Auth(Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")))
    try:
        auth.add_teacher(username, name, pw, tenant=a.tenant, role=a.role,
                         labs=[x.strip() for x in a.labs.split(",") if x.strip()])
    except AuthError as e:
        sys.exit(str(e))
    print(f"נשמר: {username.strip().lower()} ({name}). מסכי המורה דורשים עכשיו כניסה. הפעילו מחדש את השרת אם הוא רץ.")


if __name__ == "__main__":
    main()
