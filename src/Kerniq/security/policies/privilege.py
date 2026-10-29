"""Privilege-escalation commands are denied unless host freedom is on."""

from __future__ import annotations

from .common import class_pattern

LABEL = "privilege escalation"

BODY = r"sudo|doas|pkexec|runas|gsudo|machinectl|su|chroot|nsenter|unshare"

PATTERN = class_pattern(BODY)
