"""Add a teacher account (or reset its password).

Run from the repository root:
    python3 tools/add_teacher.py rita "ריטה"
The password is asked twice and never shown. It is stored only as a salted PBKDF2 hash in
var/state/teachers.json (or $STATE_DIR/teachers.json). Once one account exists, the teacher
screens require login (demo mode ends).
"""
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.auth import Auth, AuthError  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    username = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else username
    pw = getpass.getpass("סיסמה (8 תווים לפחות): ")
    if pw != getpass.getpass("שוב: "):
        sys.exit("הסיסמאות לא זהות.")
    auth = Auth(Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")))
    try:
        auth.add_teacher(username, name, pw)
    except AuthError as e:
        sys.exit(str(e))
    print(f"נשמר: {username.strip().lower()} ({name}). מסכי המורה דורשים עכשיו כניסה. הפעילו מחדש את השרת אם הוא רץ.")


if __name__ == "__main__":
    main()
