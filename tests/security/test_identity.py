"""Host-identity class is denied unless host freedom is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.identity import LABEL, PATTERN


def test_identity_class_matches_host_probes():
    for command in ("uname -a", "whoami", "hostname", "id", "printenv"):
        assert PATTERN.search(command), command


def test_identity_commands_are_denied():
    for command in ("uname -a", "whoami", "hostname", "id", "lsb_release -a"):
        verdict = assess_command(command)
        assert verdict.allowed is False, command
        assert LABEL in (verdict.reason or "") or "denied" in (verdict.reason or "")
