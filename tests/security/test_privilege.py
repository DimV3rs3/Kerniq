"""Privilege-escalation class is denied unless host freedom is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.privilege import LABEL, PATTERN


def test_privilege_class_matches_escalators():
    for command in ("sudo id", "doas ls", "pkexec whoami", "su -", "chroot /"):
        assert PATTERN.search(command), command


def test_privilege_commands_are_denied():
    for command in ("sudo -n true", "doas ls", "pkexec ls", "su root"):
        verdict = assess_command(command)
        assert verdict.allowed is False, command
        assert LABEL in (verdict.reason or "") or "Privileged" in (verdict.reason or "")


def test_privilege_wrappers_cannot_hide_escalation():
    for command in ("command sudo id", "nice -n 5 sudo ls", "exec sudo whoami"):
        assert assess_command(command).allowed is False, command
