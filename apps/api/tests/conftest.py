import os
import sys
import tempfile
from pathlib import Path

# Tests never write into the real var/state folder.
os.environ.setdefault("STATE_DIR", tempfile.mkdtemp(prefix="lab-state-"))
# Tests run the open demo mode unless a test turns it off; plain http test client.
os.environ.setdefault("DEMO", "1")
os.environ.setdefault("COOKIE_SECURE", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent))
