#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-restart}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-7892}"
PYTHON="${PYTHON:-/root/ctw-venv/bin/python}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$PYTHON" ]; then
  echo "Could not find executable Python at: $PYTHON" >&2
  exit 1
fi

"$PYTHON" "$PROJECT_ROOT/tools/run_studio_dev.py" "$COMMAND" --host "$HOST" --port "$PORT"
