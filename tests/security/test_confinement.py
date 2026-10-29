"""The model stays inside ./workspace unless the desktop host-freedom switch is on."""

from __future__ import annotations

from Kerniq.security.command_guard import assess_command
from Kerniq.security.pathmask import alias_attachments, scrub_for_model
from Kerniq.security.policy import SecurityPolicy


HOST_COMMANDS = [
    "iptables -t filter -L -n -v",
    'iptables -t nat -L -n -v',
    "ip addr show",
    "ip route show table all",
    "ip rule show",
    "id",
    "id; sudo -n true",
    "sudo -n true",
    "sudo iptables -t filter -vnL",
    "sudo iptables -t mangle -vnL TP_MARK",
    "systemctl is-active dnsmasq",
    "systemctl is-active hostapd",
    "ss -tuln",
    "sudo tcpdump -i eth0 -n port 443 -c 10",
    "uname -a",
    "whoami",
    "hostname",
    "cat /etc/passwd",
    "ps aux",
    "env",
    "printenv",
]


def test_host_commands_from_the_field_are_denied():
    for command in HOST_COMMANDS:
        verdict = assess_command(command)
        assert verdict.allowed is False, command


def test_workspace_commands_stay_allowed():
    for command in ("ls -la", "pwd", "python script.py", "Get-ChildItem .", "Get-Date", "echo hello"):
        assert assess_command(command).allowed, command


def test_host_freedom_allows_inspection_but_not_destruction():
    assert assess_command("sudo iptables -t filter -L -n", host_freedom=True).allowed
    assert assess_command("ip addr show", host_freedom=True).allowed
    assert assess_command("cat /etc/hostname", host_freedom=True).allowed
    for command in (
        "rm -rf /",
        "sudo rm -rf /",
        "mkfs.ext4 /dev/sda",
        "shutdown -h now",
        "dd if=/dev/zero of=/dev/sda",
        ":(){ :|:& };:",
    ):
        assert assess_command(command, host_freedom=True).allowed is False, command


def test_server_policy_cannot_enable_host_freedom(tmp_path):
    policy = SecurityPolicy(tmp_path, host_freedom=False)
    assert policy.terminal_block_reason("sudo id")
    loose = SecurityPolicy(tmp_path, host_freedom=True)
    assert loose.terminal_block_reason("sudo id") is None
    assert loose.terminal_block_reason("rm -rf /")


def test_command_output_hides_the_real_directory(tmp_path):
    workspace = tmp_path / "proj" / "workspace"
    workspace.mkdir(parents=True)
    leaked = f"cwd {workspace} and home files"
    masked = scrub_for_model(leaked, workspace=workspace, reveal=False)
    assert str(workspace) not in masked
    assert "./workspace" in masked
    revealed = scrub_for_model(leaked, workspace=workspace, reveal=True)
    assert str(workspace) in revealed


def test_attachment_names_do_not_keep_the_host_path():
    mapping = alias_attachments([r"C:\Users\ada\Desktop\notes.txt", "/var/secret/notes.txt"])
    assert set(mapping) == {"./attachments/notes.txt", "./attachments/notes-2.txt"}
    assert all("Users" not in key and "secret" not in key for key in mapping)


def test_wrappers_cannot_hide_a_privileged_command():
    for command in (
        "command sudo id",
        "command -v iptables",
        "exec iptables -L",
        "nice -n 5 iptables -L",
        "busybox ip addr",
        "xargs ss -tuln",
        "type uname",
    ):
        assert assess_command(command).allowed is False, command


def test_host_freedom_file_tools_keep_the_os_closed(tmp_path):
    import asyncio

    from Kerniq.tools.packs.filesystem.tools import FileSystemTools

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "notes.txt"
    outside.write_text("hello", encoding="utf-8")
    locked = {tool.name: tool for tool in FileSystemTools(str(workspace)).get_tools()}
    free = {
        tool.name: tool
        for tool in FileSystemTools(str(workspace), policy=SecurityPolicy(workspace, host_freedom=True)).get_tools()
    }

    async def read(tool, path):
        return await tool.execute({"path": path}, None)

    denied = asyncio.run(read(locked["read_file"], str(outside)))
    assert denied.success is False
    assert str(outside) not in (denied.human_readable or "")
    opened = asyncio.run(read(free["read_file"], str(outside)))
    assert opened.success is True
    assert "hello" in (opened.human_readable or "")
    blocked = asyncio.run(free["write_file"].execute({"path": "/etc/kerniq-nope", "content": "x"}, None))
    assert blocked.success is False
    assert "operating-system" in (blocked.human_readable or "").lower()
