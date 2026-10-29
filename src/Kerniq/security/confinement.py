"""Command confinement. Not an OS sandbox.

The default posture is that a shell may work inside ./workspace and
./attachments and must not inspect or administer the host. Host freedom
(desktop only) relaxes that, except for commands that wipe disks, remove
the operating system, or shut the machine down.

Host-administration classes live in ``security.policies`` (one module per
class). This module is the public facade.
"""

from __future__ import annotations

import re
from pathlib import Path

from .policies import HOST_CLASSES, flatten_quotes, strip_wrappers
from .policies.destructive import OS_WRITE_PREFIXES, destructive_reason
from .policies.internals import (
    BASE64_EXEC,
    ESCALATE,
    ENV_DUMP,
    PRIVATE_INTERNALS,
    WINDOWS_NET,
)

# Re-export so existing callers keep working.
__all__ = [
    "confined_reason",
    "destructive_reason",
    "os_write_forbidden",
]


def os_write_forbidden(path: Path | str) -> str | None:
    """Refuse a host-freedom write that would change the operating system."""
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        resolved = Path(path)
    posix = resolved.as_posix()
    if posix in {"/", "/."} or re.fullmatch(r"[A-Za-z]:/", posix):
        return "Refusing to change the filesystem root."
    for root in OS_WRITE_PREFIXES:
        if posix == root or posix.startswith(root + "/"):
            return "Refusing to change operating-system files."
    windows = str(resolved).replace("/", "\\").lower()
    for marker in ("\\windows\\", "\\system32\\", "\\syswow64\\"):
        if marker in windows:
            return "Refusing to change operating-system files."
    return None


def confined_reason(command: str) -> str | None:
    """Why a host-inspection or privileged command is denied. Empty if allowed."""
    text = flatten_quotes(command or "")
    if PRIVATE_INTERNALS.search(text):
        return "Commands that touch Kerniq internals are denied."
    if BASE64_EXEC.search(text):
        return "Decoding a payload into the shell is denied."
    if ENV_DUMP.search(text):
        return "Dumping the environment is denied. It would reveal host paths."
    if WINDOWS_NET.search(text):
        return "Windows account and service commands are denied."
    if ESCALATE.search(text):
        return (
            "Privileged commands are denied. The shell may work only inside "
            "./workspace and ./attachments."
        )
    stripped = strip_wrappers(text)
    for candidate in (text, stripped):
        for label, pattern in HOST_CLASSES:
            match = pattern.search(candidate)
            if not match:
                continue
            name = match.group(0).split()[-1]
            return (
                f"'{name}' is denied ({label}). The shell may work only inside "
                "./workspace and ./attachments. It cannot inspect or administer the host."
            )
    return None
