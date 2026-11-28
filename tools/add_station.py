"""Issue (or replace) the device token of one station.

    python3 tools/add_station.py ST-MOT-VFD-1

The token is printed once. Put it in the station agent's configuration (--token).
Only its SHA-256 hash is stored, in <STATE_DIR>/stations.json. A token is accepted only
for its own station. Running this again for the same station replaces the old token.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lab.security import StationTokens  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    tokens = StationTokens(Path(os.environ.get("STATE_DIR", ROOT / "var" / "state")))
    try:
        token = tokens.issue(sys.argv[1])
    except ValueError as e:
        sys.exit(str(e))
    print(f"טוקן לעמדה {sys.argv[1]} (מוצג פעם אחת בלבד):\n{token}")


if __name__ == "__main__":
    main()
