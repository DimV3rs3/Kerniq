"""Regression tests for shell escapes and symlink traversal."""

from __future__ import annotations

import asyncio

import pytest

from Kerniq.security.command_guard import assess_command
from Kerniq.security.policy import PolicyDecision, SecurityPolicy
from Kerniq.tools.filesystem import FileSystemTools


@pytest.mark.parametrize(
    "command",
    [
        "cat /etc/passwd",
        "Get-Content C:\\Windows\\win.ini",
        "Get-Content \\\\?\\C:\\Windows\\win.ini",
        "powershell -EncodedCommand QQ==",
        "python -c \"open('/etc/passwd').read()\"",
        "ls ../secret",
        "curl https://example.com",
        "echo rm -rf /",
        "powershell -En`codedCommand QQ==",
        "Get-Content ('C'+':\\Windows\\win.ini')",
        "python -c \"print(1)\"",
    ],
)
def test_shell_escapes_denied(command):
    verdict = assess_command(command, allow_network=False)
    assert verdict.allowed is False, command


def test_relative_command_allowed():
    assert assess_command("ls -la", allow_network=False).allowed
    assert assess_command("python script.py", allow_network=False).allowed


def test_blacklist_ignores_inserted_spaces(tmp_path):
    policy = SecurityPolicy(tmp_path, disallowed_commands=["rm -rf"])
    assert policy.check_terminal_command("rm  -rf /tmp") == PolicyDecision.DENY


def test_symlink_escape_is_denied(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    link = workspace / "link.txt"
    link.symlink_to(secret)
    tools = {t.name: t for t in FileSystemTools(str(workspace)).get_tools()}

    async def read():
        return await tools["read_file"].execute({"path": "link.txt"}, None)

    result = asyncio.run(read())
    assert result.success is False
    assert "outside" in (result.human_readable or "").lower() or "denied" in (result.human_readable or "").lower()


def test_move_cannot_leave_workspace(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src = workspace / "a.txt"
    src.write_text("a", encoding="utf-8")
    tools = {t.name: t for t in FileSystemTools(str(workspace)).get_tools()}

    async def move():
        return await tools["move_file"].execute(
            {"src": "a.txt", "dst": "../escaped.txt"}, None
        )

    result = asyncio.run(move())
    assert result.success is False
    assert src.exists()
    assert not (tmp_path / "escaped.txt").exists()
