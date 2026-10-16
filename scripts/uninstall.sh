#!/usr/bin/env bash
# Remove Kerniq's venv and only the packages this install added.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WIPE=0
if [ "${1:-}" = "--wipe-project" ] || [ "${1:-}" = "wipe" ]; then
  WIPE=1
fi
can_run() {
  [ -n "${1:-}" ] || return 1
  if [ -x "$1" ]; then
    return 0
  fi
  command -v "$1" >/dev/null 2>&1
}
MANIFEST="$ROOT/.kerniq/install.json"
PY=""
READER=""
if [ -x "$ROOT/.venv/bin/python" ]; then
  READER="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  READER="python3"
elif command -v python >/dev/null 2>&1; then
  READER="python"
elif [ -x "$ROOT/.kerniq/runtime/python/bin/python3" ]; then
  READER="$ROOT/.kerniq/runtime/python/bin/python3"
fi
if [ -n "$READER" ] && [ -f "$MANIFEST" ]; then
  recorded="$("$READER" -c "import json,sys; print(json.load(open(sys.argv[1])).get('python',''))" "$MANIFEST" 2>/dev/null || true)"
  if [ -n "$recorded" ] && [ -x "$recorded" ]; then
    PY="$recorded"
  fi
fi
if [ -z "$PY" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
  else
    PY="python"
  fi
fi

if can_run "$PY"; then
  echo "Resetting Kerniq settings..."
  if [ "$WIPE" = "1" ]; then
    "$PY" -m Kerniq uninstall -y --wipe-project || true
    echo "Project wipe was requested. Source, venv, and the private Python copy go with it."
    exit 0
  fi
  "$PY" -m Kerniq uninstall -y || true
fi

if [ "$WIPE" = "1" ]; then
  exit 0
fi

created_venv=0
created_runtime=0
if [ -f "$MANIFEST" ] && can_run "$PY"; then
  created_venv="$("$PY" -c "import json,sys; print(1 if json.load(open(sys.argv[1])).get('created_venv', False) else 0)" "$MANIFEST" 2>/dev/null || echo 0)"
  created_runtime="$("$PY" -c "import json,sys; print(1 if json.load(open(sys.argv[1])).get('created_runtime') else 0)" "$MANIFEST" 2>/dev/null || echo 0)"
fi

if [ "$created_venv" = "1" ] && [ -d "$ROOT/.venv" ]; then
  echo "Removing .venv and the libraries installed into it."
  rm -rf "$ROOT/.venv"
elif can_run "$PY"; then
  echo "Removing only packages Kerniq installed. Packages that were already here stay."
  names="$("$PY" "$ROOT/scripts/env_manifest.py" remove-new "$MANIFEST" || true)"
  if [ -n "$names" ]; then
    # shellcheck disable=SC2086
    "$PY" -m pip uninstall -y $names || true
  fi
fi

if [ "$created_runtime" = "1" ]; then
  echo "Removing the private Python copy Kerniq downloaded."
  rm -rf "$ROOT/.kerniq/runtime"
fi
rm -f "$MANIFEST" "$ROOT/.kerniq/kerniq" "$ROOT/.kerniq/kerniq.cmd"
echo "Done."
