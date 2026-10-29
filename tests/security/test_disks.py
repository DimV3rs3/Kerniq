"""Disks-and-hardware class is denied unless host freedom is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.disks import LABEL, PATTERN


def test_disks_class_matches_hardware_probes():
    for command in ("lsblk", "df -h", "lspci", "mount", "fdisk -l"):
        assert PATTERN.search(command), command


def test_disks_commands_are_denied():
    for command in ("lsblk", "df -h", "dmidecode", "findmnt"):
        verdict = assess_command(command)
        assert verdict.allowed is False, command
        assert LABEL in (verdict.reason or "") or "denied" in (verdict.reason or "")
