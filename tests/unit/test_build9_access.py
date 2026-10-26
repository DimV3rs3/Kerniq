"""Sandbox isolation, external folders, listen addresses, and database setup."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from Kerniq.sandbox.guard import host_launch_allowed, sitecustomize_source
from Kerniq.sandbox.venv import apply_sandbox_env
from Kerniq.security.command_guard import assess_command
from Kerniq.security.policy import PolicyDecision, SecurityPolicy
from Kerniq.security.task_scope import use_task
from Kerniq.server.database import build_mysql_url, database_name_ok, scan_engines
from Kerniq.server.firewall import listen_lines
from Kerniq.server.store import parse_mysql_url
from Kerniq.settings.browser import overlay_settings, public_settings
from Kerniq.settings.ui_store import UiSettings
from Kerniq.tools.packs.filesystem.tools import ReadFileTool, WriteFileTool


def test_host_launch_refuses_cmd_and_dotnet(tmp_path):
    root = tmp_path / "venv"
    (root / "bin").mkdir(parents=True)
    ok, reason = host_launch_allowed("cmd", root)
    assert ok is False and "sandbox" in reason.lower()
    ok, reason = host_launch_allowed("dotnet", root)
    assert ok is False
    ok, reason = host_launch_allowed("python", root, shell=True)
    assert ok is False
    ok, _reason = host_launch_allowed("python", root)
    assert ok is True
    outside = tmp_path / "dotnet.exe"
    outside.write_text("nope", encoding="utf-8")
    ok, reason = host_launch_allowed(str(outside), root)
    assert ok is False and "outside" in reason.lower()


def test_sitecustomize_blocks_cmd(tmp_path):
    script = tmp_path / "check.py"
    script.write_text(
        sitecustomize_source()
        + "\nimport os, subprocess\n"
        + f"os.environ['KERNIQ_SANDBOX'] = {str(tmp_path / 'venv')!r}\n"
        + "try:\n"
        + "    subprocess.run(['cmd', '/c', 'echo', 'hi'], check=False)\n"
        + "except PermissionError:\n"
        + "    raise SystemExit(0)\n"
        + "raise SystemExit(2)\n",
        encoding="utf-8",
    )
    import subprocess

    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_sandbox_path_hides_the_host(tmp_path, monkeypatch):
    bindir = tmp_path / ("Scripts" if os.name == "nt" else "bin")
    bindir.mkdir()
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    python.write_text("x", encoding="utf-8")
    monkeypatch.setattr("Kerniq.sandbox.venv.ensure_sandbox_python", lambda workspace: python)
    monkeypatch.setattr("Kerniq.sandbox.venv.install_guard", lambda _python: None)
    env = apply_sandbox_env({"PATH": "/usr/bin:/opt/dotnet", "PYTHONPATH": "/host"}, tmp_path)
    assert "/usr/bin" not in env["PATH"]
    assert "dotnet" not in env["PATH"]
    assert str(bindir.resolve()) in env["PATH"]
    assert "PYTHONPATH" not in env
    assert env["PYTHONNOUSERSITE"] == "1"


def test_python_dash_s_is_denied():
    verdict = assess_command("python -S script.py")
    assert verdict.allowed is False


def test_external_directory_is_read_only_until_the_flag_is_off(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    external = tmp_path / "outside"
    nested = external / "sub"
    nested.mkdir(parents=True)
    target = nested / "note.txt"
    target.write_text("hi", encoding="utf-8")
    reader = ReadFileTool(workspace)
    writer = WriteFileTool(workspace)
    task = SimpleNamespace(
        metadata={"external_files": [str(external)], "external_read_only": True},
        strict_attachments=False,
        allowed_files=[],
    )
    with use_task(task):
        assert reader._safe_path(str(target)).read_text(encoding="utf-8") == "hi"
        with pytest.raises(PermissionError):
            writer._safe_path(str(target))
    task.metadata["external_read_only"] = False
    with use_task(task):
        path = writer._safe_path(str(target))
        path.write_text("changed", encoding="utf-8")
    assert target.read_text(encoding="utf-8") == "changed"


def test_policy_denies_external_tree_while_read_only(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    external = tmp_path / "outside"
    external.mkdir()
    child = external / "a.txt"
    policy = SecurityPolicy(workspace_root=workspace, auto_approve_up_to="high")

    class Tool:
        name = "write_file"
        tool_id = "write_file"
        risk_level = "medium"
        cfg_auto_accept = False

    task = SimpleNamespace(
        metadata={"external_files": [str(external)], "external_read_only": True},
    )
    with use_task(task):
        decision = policy.evaluate_tool_call(
            "write_file", {"path": str(child)}, "medium", tool=Tool()
        )
    assert decision == PolicyDecision.DENY
    task.metadata["external_read_only"] = False
    with use_task(task):
        decision = policy.evaluate_tool_call(
            "write_file", {"path": str(child)}, "medium", tool=Tool()
        )
    assert decision == PolicyDecision.ALLOW


def test_listen_lines_tell_a_windows_pc_the_lan_address(monkeypatch):
    monkeypatch.setattr("Kerniq.server.firewall.lan_ipv4s", lambda: ["192.168.1.20"])
    lines = listen_lines("0.0.0.0", 8765, firewall_note="sudo ufw allow 8765/tcp")
    text = "\n".join(lines)
    assert "http://192.168.1.20:8765" in text
    assert "Windows" in text
    assert "private" in text.lower()
    assert "sudo ufw allow 8765/tcp" in text
    local = "\n".join(listen_lines("127.0.0.1", 8765))
    assert "only reachable from this computer" in local


def test_mysql_url_round_trip_and_name_check():
    assert database_name_ok("kerniq")
    assert not database_name_ok("kerniq;drop")
    assert not database_name_ok("bad-name")
    url = build_mysql_url("127.0.0.1", 3306, "root", "p@ss word", "kerniq")
    parsed = parse_mysql_url(url)
    assert parsed["user"] == "root"
    assert parsed["password"] == "p@ss word"
    assert parsed["database"] == "kerniq"
    assert parsed["port"] == 3306
    with pytest.raises(ValueError):
        build_mysql_url("127.0.0.1", 3306, "root", "x", "bad name")


def test_scan_marks_postgres_unsupported(monkeypatch):
    monkeypatch.setattr("Kerniq.server.database.shutil.which", lambda name: "/usr/bin/psql" if name == "psql" else None)
    monkeypatch.setattr("Kerniq.server.database.importlib.util.find_spec", lambda name: None)
    rows = {row["id"]: row for row in scan_engines()}
    assert "mysql" not in rows
    assert rows["postgres"]["supported"] is False


def test_server_settings_drop_the_api_token_and_keep_it_in_memory():
    ui = UiSettings()
    ui.api.api_token = "sk-secret"
    shown = public_settings(ui.model_dump(), server_mode=True)
    assert shown["api"]["api_token"] == ""
    assert shown["client_owned"] is True
    fresh = UiSettings()
    fresh.api.api_token = ""
    overlaid = overlay_settings(fresh, {"api": {"api_token": "sk-from-browser", "api_token_sealed": "nope"}})
    assert overlaid.api.api_token == "sk-from-browser"
    assert fresh.api.api_token == ""
    assert not hasattr(overlaid.api, "api_token_sealed") or overlaid.api.api_token != "nope"
