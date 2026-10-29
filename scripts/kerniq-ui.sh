#!/usr/bin/env bash
# Start the Web UI in the background. The working directory is the project, not scripts/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/logs"
if [ -f "$ROOT/.kerniq/install.json" ] && grep -q '"created_venv": true' "$ROOT/.kerniq/install.json" && [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
LOG="$ROOT/logs/ui.log"
PIDFILE="$ROOT/logs/ui.pid"
if [ -f "$PIDFILE" ]; then
  old="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
    echo "Kerniq UI is already running (pid $old). Log: $LOG"
    exit 0
  fi
fi
setsid "$PY" -m Kerniq plugins ui >>"$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
echo "Kerniq UI starting in the background (pid $(cat "$PIDFILE"))."
echo "Log: $LOG"
echo "Open http://127.0.0.1:8765"