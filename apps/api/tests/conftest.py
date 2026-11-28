import os
import sys
import tempfile
from pathlib import Path

# Tests never write into the real var/state folder.
os.environ.setdefault("STATE_DIR", tempfile.mkdtemp(prefix="lab-state-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
