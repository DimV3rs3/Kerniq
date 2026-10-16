#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -f "$ROOT/.kerniq/install.json" ] && grep -q '"created_venv": true' "$ROOT/.kerniq/install.json" && [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
nohup "$PY" -m Kerniq plugins ui >/tmp/kerniq-ui.log 2>&1 &
echo "Kerniq UI starting (log: /tmp/kerniq-ui.log). Open http://127.0.0.1:8765"