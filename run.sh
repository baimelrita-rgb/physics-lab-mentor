#!/usr/bin/env bash
# Start the lab mentor on this computer: installs what is missing, builds the screens, runs the server.
# Usage:  ./run.sh            then open http://localhost:8000
# Demo:   REPLAY_SPEED=4 STUCK_SECONDS=60 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install --quiet -r apps/api/requirements.txt
if [ ! -f apps/web/dist/index.html ] || [ -n "$(find apps/web/src -newer apps/web/dist/index.html)" ]; then
  (cd apps/web && npm install --no-audit --no-fund && npm run build)
fi
cd apps/api
echo "Lab mentor: http://localhost:${PORT:-8000}  (Claude: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo on || echo off, approved texts only))"
exec python3 -m uvicorn lab.app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
