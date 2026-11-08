"""Start child processes without opening a console window."""

from __future__ import annotations

import os
import subprocess

NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010

_INSTALLED = False


def quiet_flags(flags: int) -> int:
    """Hide a console. CREATE_NEW_CONSOLE cancels CREATE_NO_WINDOW, so it is stripped."""
    return (int(flags or 0) & ~CREATE_NEW_CONSOLE) | NO_WINDOW


def hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    return {"creationflags": NO_WINDOW, "startupinfo": info}


def hidden_run(args: list, **kwargs):
    extra = hidden_kwargs()
    flags = quiet_flags(kwargs.get("creationflags", 0) | extra.get("creationflags", 0))
    if flags:
        kwargs["creationflags"] = flags
    if "startupinfo" not in kwargs and "startupinfo" in extra:
        kwargs["startupinfo"] = extra["startupinfo"]
    return subprocess.run(args, **kwargs)


def install_hidden_subprocess() -> None:
    """Every child of this process stays off the Windows console.

    Git, icacls, taskkill, and PowerShell are console programs. Python opens
    a window for them unless CreateProcess is told not to. CREATE_NEW_CONSOLE
    (0x10) wins over CREATE_NO_WINDOW, so that flag is removed.

    Popen has to stay a class. asyncio on Windows subclasses it while the
    process is starting. Replacing it with a function makes that import fail
    and Kerniq never opens.
    """
    global _INSTALLED
    if _INSTALLED or os.name != "nt":
        return
    original = subprocess.Popen
    if not isinstance(original, type):
        return
    _INSTALLED = True

    class _HiddenPopen(original):
        def __init__(self, *args, **kwargs):
            extra = hidden_kwargs()
            kwargs["creationflags"] = quiet_flags(
                int(kwargs.get("creationflags") or 0) | int(extra.get("creationflags") or 0)
            )
            if "startupinfo" not in kwargs and extra.get("startupinfo") is not None:
                kwargs["startupinfo"] = extra["startupinfo"]
            super().__init__(*args, **kwargs)

    _HiddenPopen.__name__ = "Popen"
    _HiddenPopen.__qualname__ = "Popen"
    subprocess.Popen = _HiddenPopen
