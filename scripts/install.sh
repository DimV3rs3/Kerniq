#!/usr/bin/env bash
# One-click Kerniq install (Linux/macOS)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
echo "Installing Kerniq editable with [dev,mcp]..."
"$PY" -m pip install -e ".[dev,mcp]"
"$PY" -m Kerniq --version
echo "Done. Try: kerniq plugins ui"
echo "Or: $PY -m Kerniq plugins ui"
