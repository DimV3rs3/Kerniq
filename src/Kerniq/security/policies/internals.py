"""Internals, environment dumps, and encoded payloads are always denied."""

from __future__ import annotations

import re

PRIVATE_INTERNALS = re.compile(r"(?i)(?:\.kerniq|sitecustomize)")

ENV_DUMP = re.compile(
    r"(?i)(?:"
    r"(?:^|[&|;()\n]|&&|\|\|)\s*(?:env|export)\b|"
    r"\bGet-ChildItem\b[^\n]*\benv:"
    r")"
)

WINDOWS_NET = re.compile(
    r"(?i)\bnet(?:\.exe)?\s+(?:user|localgroup|share|use|session|start|stop)\b"
)

BASE64_EXEC = re.compile(r"(?i)\bbase64\b[^\n]*\s(?:-d|--decode)\b")

ESCALATE = re.compile(r"(?i)\b(?:sudo|doas|pkexec|runas|gsudo)\b")
