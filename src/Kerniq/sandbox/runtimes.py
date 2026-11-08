"""Private Node and .NET prefixes. The shell must not see the host copies.

The language-sandbox plugin registers the filters. With no plugin, nothing
here changes PATH or commands. Core does not import that plugin by name.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

RUNTIME_DIR = ".kerniq-runtimes"

_ENV = {}
_BLOCK = {}

_NODE_FILES = ("node", "node.exe", "npm", "npm.cmd", "npx", "npx.cmd")
_DOTNET_FILES = ("dotnet", "dotnet.exe", "csc", "csc.exe", "msbuild", "msbuild.exe")


def register_language_runtime(key: str, env_filter, block_filter) -> None:
    if env_filter is not None:
        _ENV[str(key)] = env_filter
    if block_filter is not None:
        _BLOCK[str(key)] = block_filter


def unregister_language_runtime(key: str) -> None:
    _ENV.pop(str(key), None)
    _BLOCK.pop(str(key), None)


def apply_language_env(env: dict, workspace: Path) -> dict:
    out = env
    for fn in list(_ENV.values()):
        try:
            nxt = fn(out, workspace)
        except Exception:
            continue
        if isinstance(nxt, dict):
            out = nxt
    return out


def language_block_reason(command: str) -> str:
    for fn in list(_BLOCK.values()):
        try:
            reason = fn(command)
        except Exception:
            continue
        if reason:
            return str(reason)
    return ""


def runtime_root(workspace: Path) -> Path:
    return Path(workspace) / RUNTIME_DIR


def _has_any(folder: Path, names: tuple[str, ...]) -> bool:
    try:
        for name in names:
            if (folder / name).exists():
                return True
    except OSError:
        return False
    return False


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def isolate_runtime_path(env: dict, workspace: Path, *, node: bool, dotnet: bool) -> dict:
    """Prepend private shims and drop host directories that contain node or dotnet."""
    out = dict(env)
    if not node and not dotnet:
        return out
    root = runtime_root(workspace)
    bindir = ensure_shims(root, node=node, dotnet=dotnet)
    names: list[str] = []
    if node:
        names.extend(_NODE_FILES)
    if dotnet:
        names.extend(_DOTNET_FILES)
    kept = []
    raw = out.get("PATH") or ""
    for part in str(raw).split(os.pathsep):
        if not part:
            continue
        folder = Path(part)
        if _under(folder, root):
            kept.append(part)
            continue
        if _has_any(folder, tuple(names)):
            continue
        if part not in kept:
            kept.append(part)
    prefix = str(bindir)
    out["PATH"] = os.pathsep.join([prefix] + [p for p in kept if p != prefix])
    out["KERNIQ_RUNTIMES"] = str(root)
    return out


def ensure_shims(root: Path, *, node: bool = True, dotnet: bool = True) -> Path:
    bindir = root / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    if node:
        _write_shim(bindir, "node", "node")
        _write_shim(bindir, "npm", "npm")
        _write_shim(bindir, "npx", "npx")
    if dotnet:
        _write_shim(bindir, "dotnet", "dotnet")
        _write_shim(bindir, "csc", "csc")
    return bindir


def _write_shim(bindir: Path, name: str, kind: str) -> None:
    if os.name == "nt":
        path = bindir / f"{name}.cmd"
        text = _windows_shim(kind)
    else:
        path = bindir / name
        text = _posix_shim(kind)
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            return
        path.write_text(text, encoding="utf-8", newline="\n")
        if os.name != "nt":
            path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        return


def _windows_shim(kind: str) -> str:
    private = {
        "node": r"node\node.exe",
        "npm": r"node\npm.cmd",
        "npx": r"node\npx.cmd",
        "dotnet": r"dotnet\dotnet.exe",
        "csc": r"dotnet\sdk-csc.exe",
    }[kind]
    label = "Node.js" if kind in {"node", "npm", "npx"} else ".NET"
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "set \"ROOT=%~dp0..\"\r\n"
        f"set \"BIN=%ROOT%\\{private}\"\r\n"
        "if exist \"%BIN%\" (\r\n"
        "  \"%BIN%\" %*\r\n"
        "  exit /b %ERRORLEVEL%\r\n"
        ")\r\n"
        f"echo Kerniq language sandbox: {label} is not installed in this workspace. 1>&2\r\n"
        "echo Open Settings, Language sandbox, and prepare it. The copy installed on this computer is not used. 1>&2\r\n"
        "exit /b 1\r\n"
    )


def _posix_shim(kind: str) -> str:
    private = {
        "node": "node/bin/node",
        "npm": "node/bin/npm",
        "npx": "node/bin/npx",
        "dotnet": "dotnet/dotnet",
        "csc": "dotnet/sdk-csc",
    }[kind]
    label = "Node.js" if kind in {"node", "npm", "npx"} else ".NET"
    return (
        "#!/bin/sh\n"
        "ROOT=$(CDPATH= cd -- \"$(dirname \"$0\")/..\" && pwd)\n"
        f"BIN=\"$ROOT/{private}\"\n"
        "if [ -x \"$BIN\" ]; then\n"
        "  exec \"$BIN\" \"$@\"\n"
        "fi\n"
        f"echo \"Kerniq language sandbox: {label} is not installed in this workspace.\" >&2\n"
        "echo \"Open Settings, Language sandbox, and prepare it. The copy installed on this computer is not used.\" >&2\n"
        "exit 1\n"
    )


def _base_name(raw: str) -> str:
    normalized = str(raw).replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", 1)[-1]


def host_runtime_reason(command: str, runtime: Path, *, node: bool, dotnet: bool) -> str:
    """Refuse an absolute path to a host node or dotnet. A bare name hits the shim."""
    import re

    if not command or (not node and not dotnet):
        return ""
    names: list[str] = []
    if node:
        names.extend(("node", "npm", "npx", "corepack"))
    if dotnet:
        names.extend(("dotnet", "csc", "msbuild", "nuget"))
    name_re = re.compile(r"(?i)^(?:" + "|".join(names) + r")(?:\.exe|\.cmd|\.bat)?$")
    refusal = (
        "That command points at a runtime installed on this computer. "
        "Use node, npm, or dotnet without a path so the workspace sandbox runs, "
        "or prepare it under Settings, Language sandbox."
    )
    root = Path(runtime)

    def blocked(raw: str) -> str:
        raw = (raw or "").strip().strip("'\"")
        if not raw:
            return ""
        is_drive = bool(re.match(r"(?i)^[a-z]:[\\/]", raw))
        is_unc = raw.startswith("\\\\") or raw.startswith("//")
        is_unix = raw.startswith("/")
        if not (is_drive or is_unc or is_unix):
            return ""
        if not name_re.match(_base_name(raw)):
            return ""
        try:
            path = Path(raw)
        except Exception:
            return refusal
        if _under(path, root):
            return ""
        return refusal

    text = str(command)
    for match in re.finditer(r'"([^"]+)"|\'([^\']+)\'', text):
        raw = match.group(1) if match.group(1) is not None else match.group(2)
        reason = blocked(raw or "")
        if reason:
            return reason
    token = re.compile(
        r"(?i)(?:^|[\s`(=|&])((?:[a-z]:[\\/]|\\\\|//)[^\s'\"`|;]+|/[^\s'\"`|;]+)"
    )
    for match in token.finditer(text):
        reason = blocked(match.group(1))
        if reason:
            return reason
    return ""
