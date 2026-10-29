"""Shared patterns for command-position matching and wrapper stripping."""

from __future__ import annotations

import re

# Command-position match: start of the string, or after a shell separator.
# Quotes are stripped by the caller before this runs.
AT = r"(?:^|[&|;()\n]|&&|\|\|)"

WRAPPERS = (
    "command",
    "exec",
    "nohup",
    "nice",
    "time",
    "ionice",
    "stdbuf",
    "busybox",
    "setsid",
    "xargs",
    "env",
    "type",
)

STRIP_WRAPPERS = re.compile(
    r"(?i)(^|[&|;()\n]|&&|\|\|)"
    r"(\s*(?:"
    + "|".join(WRAPPERS)
    + r")\b(?:\s+(?:-\S+|\S+=\S+|\d+))*)"
)


def class_pattern(body: str) -> re.Pattern[str]:
    """Compile a host-administration class that matches at command position."""
    return re.compile(AT + r"\s*(?:" + body + r")\b", re.IGNORECASE)


def strip_wrappers(text: str) -> str:
    """Drop ``command``, ``nice``, ``busybox`` and similar prefixes.

    ``command sudo`` and ``nice -n 5 iptables`` are judged as ``sudo`` and
    ``iptables``. The separator in front of the wrapper is kept.
    """
    current = text
    for _ in range(6):
        updated = STRIP_WRAPPERS.sub(r"\1", current)
        if updated == current:
            break
        current = updated
    return current


def flatten_quotes(command: str) -> str:
    return re.sub(r"['\"`^+]", "", command or "")
