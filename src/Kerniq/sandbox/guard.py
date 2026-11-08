"""Stop the workspace sandbox from seeing the rest of the computer.

The shell PATH contains only the private venv. This module is the second
check: a Python script in that venv cannot start host programs, open paths
outside the visible folders, or load the native libraries that skip Python
(kernel32, ntdll, libc). It is not an OS sandbox. A native extension that is
already loaded can still issue a raw syscall.
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


def confine_allows(path: str, *, write: bool = False, environ: dict | None = None) -> bool:
    """True when a Python open/list may touch ``path``.

    Off unless KERNIQ_CONFINE=1. The interpreter and the sandbox stay readable
    so imports keep working. Writes stay inside the visible roots. UNC and
    extended paths are refused without asking the OS, so a share cannot look
    like it exists. ``environ`` is a snapshot: the sandbox does not trust the
    live environment, which the script can edit.
    """
    import os
    import sys
    from pathlib import Path

    env = environ if environ is not None else os.environ
    if str(env.get("KERNIQ_CONFINE") or "") != "1":
        return True
    if isinstance(path, int):
        return True
    if isinstance(path, bytes):
        text = os.fsdecode(path)
    elif isinstance(path, os.PathLike):
        raw = os.fspath(path)
        text = os.fsdecode(raw) if isinstance(raw, bytes) else str(raw)
    else:
        text = "" if path is None else str(path)
    if not text or text == "-":
        return True
    if "\x00" in text:
        return False
    # \\server\share, //server/share, \\?\C:\..., \\.\  — never stat these.
    if text.replace("\\", "/").startswith("//"):
        return False

    try:
        target = Path(text).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        target = target.resolve()
    except OSError:
        return False

    def _roots(raw: str) -> list:
        return [Path(item) for item in str(raw or "").split(os.pathsep) if item]

    visible = _roots(env.get("KERNIQ_VISIBLE") or "")
    for root in visible:
        try:
            target.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    if write:
        return False
    readable = []
    sandbox = env.get("KERNIQ_SANDBOX") or ""
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


def native_dll_blocked(name: object, *, environ: dict | None = None) -> bool:
    """True when confinement must refuse this ctypes library.

    ``None`` is libc on POSIX (dlopen NULL). kernel32, ntdll, and libc are how
    a script skips Python and calls the operating system directly.
    """
    import os

    env = environ if environ is not None else os.environ
    if str(env.get("KERNIQ_CONFINE") or "") != "1":
        return False
    if name is None:
        return True
    text = str(name).strip().strip('"').strip("'")
    if not text:
        return True
    base = text.replace("\\", "/").rsplit("/", 1)[-1].lower()
    stem = base
    for suffix in (".dll", ".exe", ".drv", ".ocx"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if ".so" in stem:
        stem = stem.split(".so", 1)[0]
    denied = {
        "kernel32", "kernelbase", "ntdll", "advapi32", "shell32", "user32",
        "msvcrt", "ucrtbase", "ws2_32", "wininet", "winhttp", "crypt32",
        "sechost", "combase", "ole32", "shlwapi", "gdi32", "setupapi",
        "cfgmgr32", "wtsapi32", "netapi32", "iphlpapi", "bcrypt",
        "libc", "libpthread", "libdl", "pthread", "dl", "c",
    }
    if stem in denied or base in denied or stem.startswith("api-ms-win-"):
        return True
    if stem.startswith("ld-linux") or stem.startswith("ld-musl"):
        return True
    if stem.startswith("python") or stem.startswith("libpython"):
        return False
    windows_drive = len(text) > 2 and text[1] == ":"
    absolute = text.startswith(("/", "\\")) or windows_drive
    if absolute and not confine_allows(text, write=False, environ=env):
        return True
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
        + "\n"
        + inspect.getsource(native_dll_blocked)
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
import io
import threading
import urllib.error
import urllib.parse
import urllib.request

try:
    import _io
except Exception:
    _io = None

_TLS = threading.local()


def _install(_launch=host_launch_allowed, _block_dll=native_dll_blocked):
    frozen = {
        "KERNIQ_CONFINE": os.environ.get("KERNIQ_CONFINE") or "",
        "KERNIQ_VISIBLE": os.environ.get("KERNIQ_VISIBLE") or "",
        "KERNIQ_SANDBOX": os.environ.get("KERNIQ_SANDBOX") or "",
        "KERNIQ_EXTERNAL_RO": os.environ.get("KERNIQ_EXTERNAL_RO") or "",
    }
    roots = [item for item in frozen["KERNIQ_EXTERNAL_RO"].split(os.pathsep) if item]
    sandbox = Path(frozen["KERNIQ_SANDBOX"]) if frozen["KERNIQ_SANDBOX"] else Path(".")
    confined = frozen["KERNIQ_CONFINE"] == "1"

    def allows(path, write=False, _fn=confine_allows, _env=frozen):
        return _fn(path, write=write, environ=_env)

    def path_text(path):
        if isinstance(path, bytes):
            return os.fsdecode(path)
        return str(path)

    def check(path, write=False, dir_fd=None, as_missing=False):
        def deny():
            if as_missing:
                raise FileNotFoundError(2, "That path is outside ./workspace.", path_text(path))
            _refuse("That path is outside ./workspace.")

        if isinstance(path, int):
            return
        if dir_fd is not None:
            try:
                absolute = os.path.isabs(path_text(path))
            except Exception:
                absolute = False
            if not absolute:
                deny()
        if not allows(path, write=write):
            deny()
        if write and external_write_blocked(path_text(path), roots):
            _refuse("External attachments are read-only.")

    def guarded(orig, write, indexes=(0,), as_missing=False):
        def wrapped(*args, **kwargs):
            if getattr(_TLS, "on", False):
                return orig(*args, **kwargs)
            _TLS.on = True
            try:
                for index in indexes:
                    if len(args) > index:
                        check(
                            args[index],
                            write=write,
                            dir_fd=kwargs.get("dir_fd"),
                            as_missing=as_missing,
                        )
            finally:
                _TLS.on = False
            return orig(*args, **kwargs)
        wrapped._kerniq_guard = True
        return wrapped

    def flags_write(flags):
        try:
            value = int(flags)
        except (TypeError, ValueError):
            return True
        bits = 0
        for name in ("O_WRONLY", "O_RDWR", "O_APPEND", "O_CREAT", "O_TRUNC"):
            bits |= getattr(os, name, 0)
        return bool(value & bits)

    def patch_fs(module):
        if module is None:
            return
        reads = ("stat", "lstat", "access", "readlink", "listdir", "scandir")
        writes = (
            "remove", "unlink", "mkdir", "rmdir", "truncate", "chmod", "chown",
            "lchmod", "chflags", "link", "symlink", "utime", "rename", "replace",
            "removedirs", "makedirs",
        )
        missing_names = {"stat", "lstat", "access", "readlink"}
        multi = {"rename", "replace", "link", "symlink"}
        for name in reads + writes:
            current = getattr(module, name, None)
            if current is None or getattr(current, "_kerniq_guard", False):
                continue
            indexes = (0, 1) if name in multi else (0,)
            setattr(
                module,
                name,
                guarded(current, name in writes, indexes, name in missing_names),
            )
        current = getattr(module, "open", None)
        if current is not None and not getattr(current, "_kerniq_guard", False):
            def _os_open(path, flags, *args, _fn=current, **kwargs):
                if getattr(_TLS, "on", False):
                    return _fn(path, flags, *args, **kwargs)
                _TLS.on = True
                try:
                    check(path, write=flags_write(flags), dir_fd=kwargs.get("dir_fd"))
                finally:
                    _TLS.on = False
                return _fn(path, flags, *args, **kwargs)
            _os_open._kerniq_guard = True
            module.open = _os_open
        current = getattr(module, "chdir", None)
        if current is not None and not getattr(current, "_kerniq_guard", False):
            module.chdir = guarded(current, False, (0,))

    patch_fs(os)
    patch_fs(sys.modules.get("posix"))
    patch_fs(sys.modules.get("nt"))

    orig_popen = subprocess.Popen
    orig_open = builtins.open

    def argv(args):
        if not args:
            return ""
        first = args[0]
        if isinstance(first, (list, tuple)):
            return str(first[0]) if first else ""
        return str(first)

    class _Popen(orig_popen):
        def __init__(self, args, *a, **kw):
            shell = bool(kw.get("shell"))
            ok, reason = _launch(argv(args), sandbox, shell=shell)
            if not ok:
                _refuse(reason or "That program is not inside the sandbox.")
            _TLS.spawn = True
            try:
                super().__init__(args, *a, **kw)
            finally:
                _TLS.spawn = False

    def _system(command):
        _refuse("A shell would see programs installed on this computer.")

    def _blocked_exec(*_a, **_k):
        _refuse("A shell would see programs installed on this computer.")

    def _open(file, mode="r", *a, **kw):
        if getattr(_TLS, "on", False):
            return orig_open(file, mode, *a, **kw)
        text = str(mode or "r")
        writing = any(ch in text for ch in "wxa+")
        _TLS.on = True
        try:
            check(file, write=writing)
        finally:
            _TLS.on = False
        return orig_open(file, mode, *a, **kw)

    subprocess.Popen = _Popen
    os.system = _system
    os.popen = _blocked_exec
    builtins.open = _open
    io.open = _open
    if _io is not None:
        try:
            _io.open = _open
        except Exception:
            pass
    pl = sys.modules.get("pathlib")
    if pl is not None:
        for acc_name in ("_NormalAccessor", "_WindowsAccessor", "_PosixAccessor"):
            acc = getattr(pl, acc_name, None)
            if acc is None:
                continue
            for name in (
                "stat", "lstat", "listdir", "scandir", "chmod", "mkdir", "unlink",
                "rmdir", "rename", "replace", "symlink", "link", "utime", "readlink",
            ):
                current = getattr(os, name, None)
                if current is not None and hasattr(acc, name):
                    try:
                        setattr(acc, name, staticmethod(current))
                    except Exception:
                        pass
            try:
                acc.open = staticmethod(_open)
            except Exception:
                pass
    for name in ("execv", "execve", "execvp", "execvpe", "spawnv", "spawnve", "spawnvp", "spawnvpe"):
        if hasattr(os, name):
            setattr(os, name, _blocked_exec)
        for mod_name in ("posix", "nt"):
            mod = sys.modules.get(mod_name)
            if mod is not None and hasattr(mod, name):
                setattr(mod, name, _blocked_exec)

    def guard_spawn(orig):
        def wrapped(*a, **k):
            if not getattr(_TLS, "spawn", False):
                _refuse("That program is not inside the sandbox.")
            return orig(*a, **k)
        return wrapped

    for mod_name, fn_name in (("_posixsubprocess", "fork_exec"), ("_winapi", "CreateProcess")):
        mod = sys.modules.get(mod_name)
        if mod is None or not hasattr(mod, fn_name):
            continue
        current = getattr(mod, fn_name)
        if not getattr(current, "_kerniq_guard", False):
            wrapped = guard_spawn(current)
            wrapped._kerniq_guard = True
            setattr(mod, fn_name, wrapped)

    if _io is not None and not getattr(io.FileIO, "_kerniq_guard", False):
        class _FileIO(_io.FileIO):
            def __init__(self, file, mode="r", closefd=True, opener=None):
                if not isinstance(file, int):
                    writing = any(ch in str(mode or "r") for ch in "wxa+")
                    check(file, write=writing)
                super().__init__(file, mode, closefd, opener)
        _FileIO._kerniq_guard = True
        io.FileIO = _FileIO
        _io.FileIO = _FileIO

    orig_urlopen = urllib.request.urlopen

    def _urlopen(url, *a, **kw):
        raw = url.full_url if hasattr(url, "full_url") else str(url or "")
        if raw.lower().startswith("file:"):
            parsed = urllib.parse.urlparse(raw)
            path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path or ""))
            if not allows(path, write=False):
                raise urllib.error.URLError("That path is outside ./workspace.")
        return orig_urlopen(url, *a, **kw)

    urllib.request.urlopen = _urlopen

    def port_blocked(address):
        if not confined or not isinstance(address, tuple) or len(address) < 2:
            return False
        try:
            port = int(address[1])
        except (TypeError, ValueError):
            return False
        # LM Studio's default port. The sandbox must not probe or use the local model API.
        return port == 1234

    import socket
    orig_connect = socket.socket.connect
    orig_connect_ex = socket.socket.connect_ex

    def _connect(self, address):
        if port_blocked(address):
            _refuse("Connections to the local model server are blocked.")
        return orig_connect(self, address)

    def _connect_ex(self, address):
        if port_blocked(address):
            _refuse("Connections to the local model server are blocked.")
        return orig_connect_ex(self, address)

    socket.socket.connect = _connect
    socket.socket.connect_ex = _connect_ex

    orig_import = builtins.__import__

    def seal_ctypes():
        if not confined:
            return
        ct = sys.modules.get("ctypes")
        raw = sys.modules.get("_ctypes")
        if ct is None:
            return

        def wrap_opener(module, attr):
            current = getattr(module, attr, None)
            if current is None or getattr(current, "_kerniq_guard", False):
                return
            def wrapped(name, *a, _fn=current, **k):
                if getattr(_TLS, "booting_ctypes", False):
                    return _fn(name, *a, **k)
                if _block_dll(name, environ=frozen):
                    _refuse("Native libraries that can leave ./workspace are blocked.")
                return _fn(name, *a, **k)
            wrapped._kerniq_guard = True
            setattr(module, attr, wrapped)

        wrap_opener(ct, "_dlopen")
        if raw is not None:
            wrap_opener(raw, "dlopen")
            wrap_opener(raw, "LoadLibrary")
        for cls_name in ("CDLL", "PyDLL", "WinDLL", "OleDLL"):
            cls = getattr(ct, cls_name, None)
            if cls is None or getattr(cls, "_kerniq_guard", False):
                continue
            orig_init = cls.__init__
            def make(fn):
                def __init__(self, name, *a, **k):
                    if getattr(_TLS, "booting_ctypes", False):
                        return fn(self, name, *a, **k)
                    if k.get("handle") is not None or (len(a) >= 2 and a[1] is not None):
                        _refuse("Native libraries that can leave ./workspace are blocked.")
                    if _block_dll(name, environ=frozen):
                        _refuse("Native libraries that can leave ./workspace are blocked.")
                    return fn(self, name, *a, **k)
                return __init__
            cls.__init__ = make(orig_init)
            cls._kerniq_guard = True

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        root = str(name or "").split(".", 1)[0]
        booting = root == "ctypes" and "ctypes" not in sys.modules
        if booting:
            _TLS.booting_ctypes = True
        try:
            mod = orig_import(name, globals, locals, fromlist, level)
        finally:
            if booting:
                _TLS.booting_ctypes = False
        if root in {"ctypes", "_ctypes"}:
            seal_ctypes()
        return mod

    builtins.__import__ = _import
    if "ctypes" in sys.modules:
        seal_ctypes()

    try:
        import importlib
        orig_reload = importlib.reload
        def _reload(module):
            loaded = orig_reload(module)
            if getattr(loaded, "__name__", "").split(".", 1)[0] in {"ctypes", "_ctypes"}:
                seal_ctypes()
            return loaded
        importlib.reload = _reload
    except Exception:
        pass


def _refuse(reason):
    raise PermissionError(reason)


_install()
del _install
'''
