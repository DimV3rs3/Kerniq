#!/usr/bin/env bash
# Install into PATH Python when it exists. Otherwise create .venv and install there.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
META="$ROOT/.kerniq"
mkdir -p "$META"
SERVER_INIT=0
for arg in "$@"; do
  if [ "$arg" = "--server" ]; then
    SERVER_INIT=1
  fi
done

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
# Debian/Ubuntu ship typing_extensions without a pip RECORD. A normal install
# tries to uninstall that file and aborts, so the kerniq command is never created.
if ! "$TARGET" -m pip install -e ".[dev,mcp]"; then
  if [ "$CREATED_VENV" = "0" ]; then
    echo "System Python refused the install. Retrying without removing Debian packages."
    "$TARGET" -m pip install --break-system-packages --ignore-installed -e ".[dev,mcp]"
  else
    exit 1
  fi
fi
echo "Creating the workspace sandbox..."
"$TARGET" -c 'import pathlib,sys; from Kerniq.sandbox.venv import prepare_workspace_at_install; prepare_workspace_at_install(pathlib.Path(sys.argv[1]))' "$ROOT" \
  || echo "Workspace sandbox was not created. Kerniq itself is installed."
echo "Scanning plugins and tool packs for Python libraries..."
"$TARGET" -c 'import pathlib,sys; from Kerniq.sandbox.deps import install_product_tree; install_product_tree(pathlib.Path(sys.argv[1]))' "$ROOT" \
  || echo "Library scan failed. Kerniq itself is installed."
"$TARGET" "$ROOT/scripts/env_manifest.py" commit "$META/install.json" "$TARGET" "$CREATED_VENV" "$CREATED_RUNTIME" "$META/before.json"
rm -f "$META/before.json"

cat > "$META/kerniq" <<EOF
#!/bin/sh
exec "$TARGET" -m Kerniq "\$@"
EOF
chmod +x "$META/kerniq"

echo
"$TARGET" -m Kerniq --version
echo "Checking plugin settings..."
"$TARGET" -c "from Kerniq.plugins.cli_settings import validate_installed_defaults; raise SystemExit(validate_installed_defaults())"
if [ "$SERVER_INIT" = "1" ]; then
  echo "Writing server defaults for plugins that declare them..."
  "$TARGET" -c "from Kerniq.plugins.cli_settings import apply_server_plugin_defaults; apply_server_plugin_defaults()"
fi

# pip without write access to system site-packages drops `kerniq` in ~/.local/bin.
# An older shell may still hash /usr/local/bin/kerniq, which then does not exist.
USER_BIN="$("$TARGET" -c 'import os,site; print(os.path.join(site.USER_BASE, "bin"))')"
mkdir -p "$USER_BIN"
ln -sf "$META/kerniq" "$USER_BIN/kerniq"
LINKED=""
IFS=':' read -r -a PATH_DIRS <<< "${PATH}"
for dir in "${PATH_DIRS[@]}"; do
  [ -n "$dir" ] && [ -d "$dir" ] && [ -w "$dir" ] || continue
  ln -sf "$META/kerniq" "$dir/kerniq"
  LINKED="$dir/kerniq"
  break
done
hash -r 2>/dev/null || true
if [ -n "$LINKED" ] && command -v kerniq >/dev/null 2>&1; then
  echo "Command: $(command -v kerniq)"
else
  echo "kerniq is not on PATH in this shell."
  echo "Use now:  $META/kerniq"
  echo "The pip copy is:  $USER_BIN/kerniq"
  echo "This shell may still remember a deleted /usr/local/bin/kerniq. Run:  hash -r"
  echo "Then add the new directory:  export PATH=\"$USER_BIN:\$PATH\""
  echo "Or install as root so the old path is replaced:  sudo ./install.sh"
fi
echo "Done."
if [ "$SERVER_INIT" = "1" ]; then
  echo "Server setup: database, UI port, user folders, and an optional Linux account."
  if [ -t 0 ]; then
    "$TARGET" -m Kerniq server init || echo "Server setup did not finish. Run: $TARGET -m Kerniq server init"
  else
    echo "No terminal, so server setup was skipped. Run: $TARGET -m Kerniq server init"
  fi
fi
if [ "$CREATED_VENV" = "1" ]; then
  echo "UI in the background (Linux):  $ROOT/scripts/kerniq-ui.sh"
  echo "UI in this terminal:  $TARGET -m Kerniq plugins ui"
  echo "Or:  $META/kerniq plugins ui --background"
else
  echo "UI in the background (Linux):  $ROOT/scripts/kerniq-ui.sh"
  echo "UI in this terminal:  python3 -m Kerniq plugins ui"
  echo "Or:  $META/kerniq plugins ui --background"
fi
