"""Commands that destroy the machine are always denied, even under host freedom."""

from __future__ import annotations

import re

DESTRUCTIVE = (
    (
        re.compile(r"(?i)\brm\b(?:\s+\S+)*\s+/(?:\s|$|\*)"),
        "Refusing to remove the filesystem root.",
    ),
    (
        re.compile(
            r"(?i)\brm\b[^\n]*(?:/(?:bin|boot|etc|lib|lib64|usr|sys|proc|dev|root|home|System)\b|\\(?:Windows|System32|SysWOW64)\b)"
        ),
        "Refusing to remove operating-system files.",
    ),
    (
        re.compile(r"(?i)\b(?:mkfs(?:\.\w+)?|wipefs|diskpart|bcdedit)\b"),
        "Refusing to format or repartition a disk.",
    ),
    (
        re.compile(r"(?i)\bformat(?:\.com)?\s+[a-z]:"),
        "Refusing to format a drive.",
    ),
    (
        re.compile(r"(?i)\bdd\b[^\n]*\bof=/dev/"),
        "Refusing to write a disk device.",
    ),
    (
        re.compile(r"(?i)>\s*/dev/(?:sd|nvme|hd|mmc|vd|xvd|disk)"),
        "Refusing to write a disk device.",
    ),
    (
        re.compile(
            r"(?i)\b(?:shutdown|reboot|poweroff|halt|Stop-Computer|Restart-Computer)\b"
        ),
        "Refusing to shut down or reboot the machine.",
    ),
    (
        re.compile(r"(?i)\binit\s+[06]\b|\bsystemctl\s+(?:poweroff|reboot|halt|kexec)\b"),
        "Refusing to shut down or reboot the machine.",
    ),
    (
        re.compile(r":\(\)\s*\{"),
        "Refusing a fork bomb.",
    ),
    (
        re.compile(
            r"(?i)\b(?:del|erase|rd|rmdir|Remove-Item)\b[^\n]*(?:\\Windows\b|\\System32\b|/etc/|/boot/|/bin/|/usr/)"
        ),
        "Refusing to remove operating-system files.",
    ),
    (
        re.compile(r"(?i)\b(?:chmod|chown)\b[^\n]*\s+/(?:\s|$)"),
        "Refusing to change ownership or mode of the filesystem root.",
    ),
    (
        re.compile(
            r"(?i)\b(?:chmod|chown|chgrp)\b[^\n]*(?:/etc/(?:passwd|shadow|sudoers|gshadow)|\\Windows\\System32\\config\\(?:SAM|SYSTEM|SECURITY))"
        ),
        "Refusing to touch account or boot databases.",
    ),
)

OS_WRITE_PREFIXES = (
    "/bin",
    "/sbin",
    "/boot",
    "/etc",
    "/lib",
    "/lib64",
    "/usr",
    "/sys",
    "/proc",
    "/dev",
    "/root",
    "/System",
    "/private/etc",
    "/private/var/db",
    "/Library/Preferences",
)


def destructive_reason(command: str) -> str | None:
    text = command or ""
    for pattern, reason in DESTRUCTIVE:
        if pattern.search(text):
            return reason
    return None
