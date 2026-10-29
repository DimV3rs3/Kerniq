"""Services-and-processes class is denied unless host freedom is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.services import LABEL, PATTERN


def test_services_class_matches_process_admin():
    for command in ("systemctl status", "ps aux", "kill 1", "journalctl -n 20"):
        assert PATTERN.search(command), command


def test_services_commands_are_denied():
    for command in ("systemctl is-active dnsmasq", "ps aux", "killall python"):
        verdict = assess_command(command)
        assert verdict.allowed is False, command
        assert LABEL in (verdict.reason or "") or "denied" in (verdict.reason or "")
