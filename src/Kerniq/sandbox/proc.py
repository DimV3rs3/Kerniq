"""Start child processes without opening a console window."""

from __future__ import annotations

import os
import subprocess

NO_WINDOW = 0x08000000


def hidden_kwargs() -> dict:
    if os.name != "nt":
        return {}
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    return {"creationflags": NO_WINDOW, "startupinfo": info}


def hidden_run(args: list, **kwargs):
    extra = hidden_kwargs()
    flags = kwargs.get("creationflags", 0) | extra.get("creationflags", 0)
    if flags:
        kwargs["creationflags"] = flags
    if "startupinfo" not in kwargs and "startupinfo" in extra:
        kwargs["startupinfo"] = extra["startupinfo"]
    return subprocess.run(args, **kwargs)
