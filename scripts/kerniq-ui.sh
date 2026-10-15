#!/usr/bin/env bash
# Launch Kerniq Web UI in background (Linux/macOS)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# Prefer nohup so terminal can close
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
nohup "$PY" -m Kerniq plugins ui >/tmp/kerniq-ui.log 2>&1 &
echo "Kerniq UI starting (log: /tmp/kerniq-ui.log). Open http://127.0.0.1:8765"
