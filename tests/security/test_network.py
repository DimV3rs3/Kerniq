"""Network-administration class is denied unless host freedom is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policies.network import LABEL, PATTERN


def test_network_class_matches_admin_tools():
    for command in ("iptables -L", "ip addr", "ss -tuln", "ufw status", "netsh interface"):
        assert PATTERN.search(command), command


def test_network_commands_are_denied():
    for command in (
        "iptables -t filter -L -n -v",
        "ip route show table all",
        "ss -tuln",
        "sudo tcpdump -i eth0 -n port 443 -c 10",
    ):
        verdict = assess_command(command)
        assert verdict.allowed is False, command
        assert LABEL in (verdict.reason or "") or "Privileged" in (verdict.reason or "") or "denied" in (verdict.reason or "")
