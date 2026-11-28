#!/usr/bin/env bash
# Records the end-to-end tutorial video on the real system (no narration: cursor + written captions).
# Needs: Node with Playwright and Chromium, ffmpeg, built web app (apps/web/dist).
# Uses its own temporary state folder: the system's real data is not touched.
# Output: tools/tutorial/out/lab-mentor-tutorial.mp4 (about 7.5 minutes).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
STATE="$(mktemp -d)"
OUT="$HERE/out"
rm -rf "$OUT" && mkdir -p "$OUT"
python3 -c "import sys; sys.path.insert(0, '$ROOT/apps/api'); from lab.auth import Auth; Auth('$STATE').add_teacher('rita', 'ריטה', 'demo-password')"
STATE_DIR="$STATE" python3 "$ROOT/tools/seed_demo_class.py" --owner rita >/dev/null
(cd "$ROOT/apps/api" && STATE_DIR="$STATE" REPLAY_SPEED=4 STUCK_SECONDS=45 python3 -m uvicorn lab.app:app --port 8003 >"$OUT/server.log" 2>&1) &
SERVER=$!
trap 'kill $SERVER 2>/dev/null; rm -rf "$STATE"' EXIT
sleep 3
node "$HERE/tour.js" http://127.0.0.1:8003 "$OUT"
ffmpeg -v error -y -i "$OUT"/*.webm -c:v libx264 -preset slow -crf 24 -pix_fmt yuv420p -movflags +faststart -an "$OUT/lab-mentor-tutorial.mp4"
rm -f "$OUT"/*.webm
echo "נוצר: $OUT/lab-mentor-tutorial.mp4"
