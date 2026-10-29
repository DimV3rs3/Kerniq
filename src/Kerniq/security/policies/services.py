"""Service and process administration is denied unless host freedom is on."""

from __future__ import annotations

from .common import class_pattern

LABEL = "services and processes"

BODY = (
    r"systemctl|service|journalctl|launchctl|"
    r"tasklist|taskkill|ps|top|htop|pgrep|pkill|killall|kill|"
    r"crontab|strace|ltrace|gdb|"
    r"Get-Process|Get-Service|Get-WmiObject|Get-CimInstance"
)

PATTERN = class_pattern(BODY)
