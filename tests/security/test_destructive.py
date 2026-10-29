"""Destructive commands stay denied even under host freedom."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.destructive import destructive_reason


def test_destructive_reason_covers_wipes_and_shutdown():
    for command in (
        "rm -rf /",
        "mkfs.ext4 /dev/sda",
        "shutdown -h now",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
    ):
        assert destructive_reason(command), command


def test_host_freedom_still_blocks_destruction():
    for command in (
        "rm -rf /",
        "sudo rm -rf /",
        "mkfs.ext4 /dev/sda",
        "shutdown -h now",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
    ):
        assert assess_command(command, host_freedom=True).allowed is False, command
