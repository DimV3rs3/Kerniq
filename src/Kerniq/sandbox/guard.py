"""Stop the workspace sandbox from seeing programs installed on the computer.

The shell PATH contains only the private venv. This module is the second
check: a Python script in that venv cannot start cmd, dotnet, or any other
executable that lives outside the venv. It is not an OS sandbox. A program
that refuses to go through Python's process API can still escape.
"""

from __future__ import annotations

import inspect
from pathlib import Path

_BLOCKED_NAMES = {
    "cmd",
    "cmd.exe",
    "powershell",
    "powershell.exe",
    "pwsh",
    "pwsh.exe",
    "dotnet",
    "dotnet.exe",
    "node",
    "node.exe",
    "npm",
    "npm.cmd",
    "bash",
    "sh",
    "wsl",
    "wsl.exe",
    "where",
    "where.exe",
    "sudo",
    "apt",
    "apt-get",
    "brew",
}


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def host_launch_allowed(executable: str, sandbox_root: Path, *, shell: bool = False) -> tuple[bool, str]:
    """True only for a program inside the sandbox venv.

    ``shell=True`` is refused: the shell would search the computer, not the venv.
    """
    if shell:
        return False, "A shell would see programs installed on this computer."
    text = str(executable or "").strip().strip('"').strip("'")
    if not text:
        return False, "Missing executable."
    name = Path(text.replace("\\", "/")).name.lower()
    root = Path(sandbox_root)
    windows_drive = len(text) > 2 and text[1] == ":"
    path = Path(text)
    if path.is_absolute() or windows_drive or text.startswith("\\\\") or text.startswith("//"):
        if _under(path, root):
            return True, ""
        return False, "That program is outside the sandbox."
    if name in _BLOCKED_NAMES:
        return False, "That program is not inside the sandbox."
    for folder in (root / "bin", root / "Scripts"):
        if (folder / text).is_file() or (folder / name).is_file():
            return True, ""
    if name in {"python", "python.exe", "python3", "pip", "pip.exe", "pip3", "pip3.exe"}:
        return True, ""
    return False, "That program is not inside the sandbox."


def path_under_any(path: str, roots: list[str]) -> bool:
    """True when ``path`` is one of the roots or a file inside one of them."""
    if not path or not roots:
        return False
    try:
        target = Path(path).resolve()
    except OSError:
        target = Path(path)
    for item in roots:
        root = Path(item)
        if target == root or _under(target, root):
            return True
    return False


def external_write_blocked(path: str, roots: list[str]) -> bool:
    """True when a write would change an attached external path."""
    return path_under_any(path, roots)


def confine_allows(path: str, *, write: bool = False) -> bool:
    """True when a Python open/list may touch ``path``.

    Off unless KERNIQ_CONFINE=1. The interpreter and the sandbox stay readable
    so imports keep working. Writes stay inside the visible roots.
    """
    import os
    import sys
    from pathlib import Path

    if os.environ.get("KERNIQ_CONFINE") != "1":
        return True
    text = str(path or "")
    if not text or text == "-":
        return True
    try:
        target = Path(text).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        target = target.resolve()
    except OSError:
        return False

    def _roots(raw: str) -> list:
        return [Path(item) for item in raw.split(os.pathsep) if item]

    visible = _roots(os.environ.get("KERNIQ_VISIBLE") or "")
    for root in visible:
        try:
            target.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    if write:
        return False
    readable = []
    sandbox = os.environ.get("KERNIQ_SANDBOX") or ""
    if sandbox:
        readable.append(Path(sandbox))
    for item in (getattr(sys, "prefix", ""), getattr(sys, "base_prefix", "")):
        if item:
            readable.append(Path(item))
    try:
        import sysconfig

        readable.append(Path(sysconfig.get_path("stdlib") or ""))
    except Exception:
        pass
    for root in readable:
        if not str(root):
            continue
        try:
            target.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def sitecustomize_source() -> str:
    """Python file installed into the venv. It does not import Kerniq."""
    logic = (
        inspect.getsource(_under)
        + "\n"
        + inspect.getsource(host_launch_allowed)
        + "\n"
        + inspect.getsource(path_under_any)
        + "\n"
        + inspect.getsource(external_write_blocked)
        + "\n"
        + inspect.getsource(confine_allows)
    )
    return _SITE_HEADER + logic + _SITE_HOOKS


_SITE_HEADER = '''"""Kerniq sandbox guard. Installed into the workspace venv."""
import builtins
import os
import subprocess
import sys
from pathlib import Path

_BLOCKED_NAMES = {
    "cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe",
    "dotnet", "dotnet.exe", "node", "node.exe", "npm", "npm.cmd",
    "bash", "sh", "wsl", "wsl.exe", "where", "where.exe",
    "sudo", "apt", "apt-get", "brew",
}

'''

_SITE_HOOKS = '''
def _sandbox():
    raw = os.environ.get("KERNIQ_SANDBOX") or ""
    return Path(raw) if raw else Path(".")


def _roots():
    raw = os.environ.get("KERNIQ_EXTERNAL_RO") or ""
    return [item for item in raw.split(os.pathsep) if item]


def _argv(args):
    if not args:
        return ""
    first = args[0]
    if isinstance(first, (list, tuple)):
        return str(first[0]) if first else ""
    return str(first)


_ORIG_POPEN = subprocess.Popen
_ORIG_SYSTEM = os.system
_ORIG_OPEN = builtins.open


def _refuse(reason):
    raise PermissionError(reason)


class _Popen(_ORIG_POPEN):
    def __init__(self, args, *a, **kw):
        shell = bool(kw.get("shell"))
        ok, reason = host_launch_allowed(_argv(args), _sandbox(), shell=shell)
        if not ok:
            _refuse(reason or "That program is not inside the sandbox.")
        super().__init__(args, *a, **kw)


def _system(command):
    _refuse("A shell would see programs installed on this computer.")


def _blocked_exec(*_a, **_k):
    _refuse("A shell would see programs installed on this computer.")


def _open(file, mode="r", *a, **kw):
    text = str(mode or "r")
    writing = any(ch in text for ch in "wxa+")
    if not confine_allows(str(file), write=writing):
        _refuse("That path is outside ./workspace.")
    if writing and external_write_blocked(str(file), _roots()):
        _refuse("External attachments are read-only.")
    return _ORIG_OPEN(file, mode, *a, **kw)


_ORIG_LISTDIR = os.listdir
_ORIG_SCANDIR = getattr(os, "scandir", None)
_ORIG_CHDIR = os.chdir


def _listdir(path=None):
    target = "." if path is None else path
    if not confine_allows(str(target), write=False):
        _refuse("That path is outside ./workspace.")
    return _ORIG_LISTDIR(path)


def _scandir(path=None):
    target = "." if path is None else path
    if not confine_allows(str(target), write=False):
        _refuse("That path is outside ./workspace.")
    return _ORIG_SCANDIR(path)


def _chdir(path):
    if not confine_allows(str(path), write=False):
        _refuse("That path is outside ./workspace.")
    return _ORIG_CHDIR(path)


subprocess.Popen = _Popen
os.system = _system
os.popen = _blocked_exec
builtins.open = _open
os.listdir = _listdir
os.chdir = _chdir
if _ORIG_SCANDIR is not None:
    os.scandir = _scandir
for _name in ("execv", "execve", "execvp", "execvpe", "spawnv", "spawnve", "spawnvp", "spawnvpe"):
    if hasattr(os, _name):
        setattr(os, _name, _blocked_exec)
'''
