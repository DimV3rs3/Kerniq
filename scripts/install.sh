#!/usr/bin/env bash
# Install into PATH Python when it exists. Otherwise create .venv and install there.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
META="$ROOT/.kerniq"
mkdir -p "$META"

py_ok() {
  local exe="$1"
  [ -n "$exe" ] || return 1
  [ -x "$exe" ] || command -v "$exe" >/dev/null 2>&1 || return 1
  "$exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1
}

find_python_on_path() {
  local c exe
  for c in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$c" >/dev/null 2>&1; then
      exe="$(command -v "$c")"
      case "$exe" in
        *.venv/*|*/.venv/*|*/.kerniq/*) continue ;;
      esac
      if py_ok "$exe"; then
        printf "%s" "$exe"
        return 0
      fi
    fi
  done
  return 1
}

find_python_off_path() {
  local c
  for c in \
    "$ROOT/.kerniq/runtime/python/bin/python3" \
    "$ROOT/.kerniq/runtime/python/bin/python"
  do
    if py_ok "$c"; then
      printf "%s" "$c"
      return 0
    fi
  done
  return 1
}

triple() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"
  case "$os-$arch" in
    Linux-x86_64) printf "%s" "x86_64-unknown-linux-gnu" ;;
    Linux-aarch64|Linux-arm64) printf "%s" "aarch64-unknown-linux-gnu" ;;
    Darwin-arm64) printf "%s" "aarch64-apple-darwin" ;;
    Darwin-x86_64) printf "%s" "x86_64-apple-darwin" ;;
    *) echo "No private Python build for $os $arch" >&2; return 1 ;;
  esac
}

install_private() {
  local trip url archive dest
  trip="$(triple)"
  echo "Python 3.11+ was not found. Downloading a private copy into .kerniq/runtime ..." >&2
  url="$(curl -fsSL -A "Kerniq-installer" \
    https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest \
    | grep -oE "https://[^\"]+cpython-3\\.1[1-4]\\.[0-9]+[^\"]+-${trip}-install_only\\.tar\\.gz" \
    | head -n 1 || true)"
  if [ -z "$url" ]; then
    echo "Could not find a Python build for $trip" >&2
    return 1
  fi
  archive="$META/python.tar.gz"
  echo "Downloading $url" >&2
  curl -fL --retry 3 -A "Kerniq-installer" -o "$archive" "$url"
  dest="$META/runtime"
  rm -rf "$dest"
  mkdir -p "$dest"
  tar -xzf "$archive" -C "$dest"
  rm -f "$archive"
  if [ -x "$dest/python/bin/python3" ]; then
    printf "%s" "$dest/python/bin/python3"
  else
    echo "Downloaded Python has no bin/python3" >&2
    return 1
  fi
}

CREATED_RUNTIME=0
CREATED_VENV=0
if TARGET="$(find_python_on_path)"; then
  echo "Python is on PATH. Installing into that interpreter. No venv."
  echo "Using $TARGET"
else
  echo "Python is not on PATH. Kerniq will use a project .venv."
  if ! BASE="$(find_python_off_path)"; then
    BASE="$(install_private)"
    CREATED_RUNTIME=1
  fi
  echo "Using $BASE to create the venv"
  TARGET="$ROOT/.venv/bin/python"
  if ! py_ok "$TARGET"; then
    rm -rf "$ROOT/.venv"
    echo "Creating .venv"
    "$BASE" -m venv "$ROOT/.venv"
    CREATED_VENV=1
  fi
fi
if ! "$TARGET" -m pip --version >/dev/null 2>&1; then
  "$TARGET" -m ensurepip --upgrade
fi

"$TARGET" "$ROOT/scripts/env_manifest.py" freeze "$TARGET" > "$META/before.json"
echo "Installing with python -m pip. Packages already present are left for uninstall to keep."
if ! "$TARGET" -m pip install -e ".[dev,mcp]"; then
  if [ "$CREATED_VENV" = "0" ]; then
    echo "Retrying with --break-system-packages"
    "$TARGET" -m pip install --break-system-packages -e ".[dev,mcp]"
  else
    exit 1
  fi
fi
echo "Scanning plugins and tool packs for Python libraries..."
"$TARGET" -c 'import pathlib,sys; from Kerniq.sandbox.deps import install_product_tree; install_product_tree(pathlib.Path(sys.argv[1]))' "$ROOT" \
  || echo "Library scan failed. Kerniq itself is installed; a plugin can still install its own libraries on load."
"$TARGET" "$ROOT/scripts/env_manifest.py" commit "$META/install.json" "$TARGET" "$CREATED_VENV" "$CREATED_RUNTIME" "$META/before.json"
rm -f "$META/before.json"

cat > "$META/kerniq" <<EOF
#!/bin/sh
exec "$TARGET" -m Kerniq "\$@"
EOF
chmod +x "$META/kerniq"

echo
"$TARGET" -m Kerniq --version
echo "Done."
if [ "$CREATED_VENV" = "1" ]; then
  echo "UI:  $TARGET -m Kerniq plugins ui"
  echo "Or:  $META/kerniq plugins ui"
else
  echo "UI:  python3 -m Kerniq plugins ui"
  echo "Or:  $META/kerniq plugins ui"
fi
