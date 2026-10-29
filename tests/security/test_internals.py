"""Internals, environment dumps, and encoded payloads are always denied."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command


def test_environment_dump_is_denied():
    for command in ("env", "printenv", "export FOO=1"):
        assert assess_command(command).allowed is False, command


def test_private_internals_are_denied():
    assert assess_command("cat .kerniq/secrets").allowed is False
    assert assess_command("python -c 'import sitecustomize'").allowed is False
