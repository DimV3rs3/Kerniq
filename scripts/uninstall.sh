#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
EXTRA=()
if [ "$1" = "--wipe-project" ] || [ "$1" = "wipe" ]; then
  EXTRA+=(--wipe-project)
fi
"$PY" -m Kerniq uninstall -y "${EXTRA[@]}" || "$PY" -m pip uninstall Kerniq -y
echo Done.
