"""Static checks for shell commands. Not an OS sandbox.

Blocks the escape classes confirmed against Kerniq (absolute/UNC paths,
PowerShell -EncodedCommand, blacklist bypass via quotes/concat, outbound
network utilities). Dynamic script engines can still touch the disk; that
limit is documented in docs/architecture/security.md.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandVerdict:
    allowed: bool
    reason: str = ""


_ENCODED = re.compile(r"(?i)(?:-encodedcommand\b|-enc\b|\bfrombase64string\b|\binvoke-expression\b|\biex\b)")
_NESTED_PS_ENC = re.compile(r"(?i)\b(?:powershell|pwsh)(?:\.exe)?\b[^\n|;]*\s-e(?:nc|ncodedcommand)?\b")
_OBFUSCATION = re.compile(r"(?i)(?:\[char\]|\[convert\]::|\[string\]::|::concat\b|-join\b)")
_DRIVE = re.compile(r"(?i)(?<![a-z0-9])[a-z]:(?!//)")
_DRIVE_TAIL = re.compile(r":\\")
_UNC = re.compile(r"(?:^|[\s'\"`(])\\\\")
_UNIX_ABS = re.compile(r"(?:^|[\s'\"`=])/(?!/)[^\s'\"`]*")
_PARENT = re.compile(r"(?:^|[\s'\"`\\/])\.\.(?:$|[\s'\"`\\/])")
_ENV = re.compile(r"(?i)(?:\$env:|%[a-z_][a-z0-9_]*%|(?<![\w])~(?=[\s/\\]|$))")
_FILE_URL = re.compile(r"(?i)\bfile://")
_INLINE_EVAL = re.compile(
    r"(?i)(?:\b(?:python3?|py|node|perl|ruby|php)\b[^\n|;]*\s-(?:c|e)\b|"
    r"\b(?:bash|sh|zsh)\b[^\n|;]*\s-c\b|"
    r"\bcmd(?:\.exe)?\b[^\n|;]*\s/c\b)"
)
_NO_SITE = re.compile(r"(?i)\b(?:python3?|py)\b[^\n|;]*\s-S\b")
_NETWORK = re.compile(
    r"(?i)\b(?:curl|wget|nc|ncat|nmap|ssh|scp|sftp|ftp|tftp|telnet|"
    r"invoke-webrequest|invoke-restmethod|iwr|irm|test-netconnection|tnc|"
    r"invoke-command|new-pssession|start-bitstransfer|"
    r"certutil|bitsadmin|nslookup|webclient)\b"
)
_SHELL_HOST = re.compile(
    r"(?i)\b(?:add-type|new-object|start-process|invoke-wmimethod|register-scheduledjob)\b"
)
_DOLLAR = re.compile(r"(?<![\w])\$([A-Za-z_][A-Za-z0-9_]*)")
_DOLLAR_OK = {"true", "false", "null", "_"}


def _normalize(text: str) -> str:
    return re.sub(r"[\s'\"`^+]+", "", (text or "").lower())


def blacklist_hit(command: str, forbidden: list[str]) -> str | None:
    """Match disallowed fragments even if quotes, spaces, or '+' were inserted."""
    raw = command or ""
    folded = raw.lower()
    compact = _normalize(raw)
    for item in forbidden:
        if not item:
            continue
        if item.lower() in folded or _normalize(item) in compact:
            return item
    return None


def _prepare(command: str) -> str:
    text = unicodedata.normalize("NFKC", command or "")
    return text.replace("`", "").replace("^", "")


def assess_command(command: str, *, allow_network: bool = False) -> CommandVerdict:
    if command is None or not str(command).strip():
        return CommandVerdict(False, "Empty command")
    cmd = _prepare(str(command))
    if "\x00" in cmd:
        return CommandVerdict(False, "NUL byte in command")
    if _ENCODED.search(cmd) or _NESTED_PS_ENC.search(cmd):
        return CommandVerdict(
            False,
            "Encoded or Invoke-Expression commands are denied (they hide the real command from policy)",
        )
    if _INLINE_EVAL.search(cmd):
        return CommandVerdict(
            False,
            "Inline eval (-c/-e) is denied; write a workspace script and run that file",
        )
    if _NO_SITE.search(cmd):
        return CommandVerdict(
            False,
            "python -S is denied; it would skip the sandbox guard",
        )
    if _OBFUSCATION.search(cmd):
        return CommandVerdict(False, "Obfuscated command construction is denied")
    if "\\\\" in cmd or _UNC.search(cmd):
        return CommandVerdict(False, "UNC or \\\\?\\ paths are outside the workspace")
    if _DRIVE.search(cmd) or _DRIVE_TAIL.search(cmd):
        return CommandVerdict(False, "Drive-letter paths are denied; use workspace-relative paths")
    if _UNIX_ABS.search(cmd):
        return CommandVerdict(False, "Absolute paths are denied; use workspace-relative paths")
    if _PARENT.search(cmd):
        return CommandVerdict(False, "Parent-directory traversal ('..') is denied in shell commands")
    if _ENV.search(cmd):
        return CommandVerdict(False, "Environment-variable or home-directory paths are denied in shell commands")
    if _FILE_URL.search(cmd):
        return CommandVerdict(False, "file:// URLs are denied")
    if _SHELL_HOST.search(cmd):
        return CommandVerdict(
            False,
            "Add-Type, New-Object, Start-Process, and similar host escapes are denied",
        )
    for match in _DOLLAR.finditer(cmd):
        if match.group(1).lower() not in _DOLLAR_OK:
            return CommandVerdict(
                False,
                "Shell variables are denied; use a workspace-relative path",
            )
    if not allow_network and _NETWORK.search(cmd):
        return CommandVerdict(
            False,
            "Network utilities are disabled for the terminal (security.allow_terminal_network = false)",
        )
    return CommandVerdict(True, "")


def escaping_symlink(root: Path, limit: int = 4000) -> str | None:
    """Return a workspace symlink whose target leaves the workspace, if any."""
    import os

    base = Path(root).resolve()
    seen = 0
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for name in list(dirnames) + list(filenames):
            seen += 1
            if seen > limit:
                return None
            path = Path(dirpath) / name
            if not path.is_symlink():
                continue
            try:
                target = path.resolve()
                target.relative_to(base)
            except Exception:
                return str(path)
    return None
