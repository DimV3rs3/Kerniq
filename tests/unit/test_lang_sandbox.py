"""Language sandbox path filter and the hidden settings catalog."""

from __future__ import annotations

import os
from pathlib import Path

from Kerniq.sandbox.proc import quiet_flags
from Kerniq.sandbox.runtimes import ensure_shims, host_runtime_reason, isolate_runtime_path, runtime_root
from Kerniq.settings.catalog import search_settings
from Kerniq.tools.packs.settings_guide.tools import FindSettingsTool


def test_quiet_flags_strip_new_console():
    assert quiet_flags(0x10) & 0x10 == 0
    assert quiet_flags(0) & 0x08000000


def test_hidden_popen_stays_a_class(monkeypatch):
    import subprocess

    from Kerniq.sandbox import proc
    from Kerniq.settings.component_store import redact_secret_fields

    class Base:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    monkeypatch.setattr(proc.os, "name", "nt")
    monkeypatch.setattr(proc, "_INSTALLED", False)
    monkeypatch.setattr(proc, "hidden_kwargs", lambda: {"creationflags": proc.NO_WINDOW})
    monkeypatch.setattr(subprocess, "Popen", Base)
    proc.install_hidden_subprocess()
    assert isinstance(subprocess.Popen, type)

    class Child(subprocess.Popen):
        pass

    child = Child(["git"], creationflags=0x10)
    assert child.kwargs["creationflags"] & proc.NO_WINDOW
    assert child.kwargs["creationflags"] & 0x10 == 0
    assert redact_secret_fields({"email": "ada@gmail.com", "password": "secret-value"}) == {
        "email": "ada@gmail.com",
        "password": "",
    }


def test_host_node_is_removed_and_shim_is_first(tmp_path: Path):
    host = tmp_path / "host-node"
    host.mkdir()
    (host / "node.exe").write_text("", encoding="utf-8")
    other = tmp_path / "other"
    other.mkdir()
    env = isolate_runtime_path(
        {"PATH": os.pathsep.join((str(host), str(other)))},
        tmp_path / "ws",
        node=True,
        dotnet=False,
    )
    parts = env["PATH"].split(os.pathsep)
    assert parts[0].replace("\\", "/").endswith(".kerniq-runtimes/bin")
    assert str(host) not in env["PATH"]
    assert str(other) in env["PATH"]
    assert (runtime_root(tmp_path / "ws") / "bin" / "node").is_file() or (
        runtime_root(tmp_path / "ws") / "bin" / "node.cmd"
    ).is_file()


def test_absolute_host_runtime_is_refused(tmp_path: Path):
    root = runtime_root(tmp_path)
    ensure_shims(root, node=True, dotnet=True)
    reason = host_runtime_reason(r'& "C:\Program Files\nodejs\node.exe" app.js', root, node=True, dotnet=True)
    assert "computer" in reason
    assert host_runtime_reason("node app.js", root, node=True, dotnet=True) == ""
    private = str(root / "node" / "node.exe")
    assert host_runtime_reason(private + " app.js", root, node=True, dotnet=True) == ""


def test_settings_catalog_link_and_hidden_tool():
    found = search_settings("temperature")
    assert found["total"] >= 1
    assert "[[setting:api:s-api-temp|Temperature]]" in found["text"]
    tool = FindSettingsTool()
    assert tool.user_hidden is True
    assert tool.agent_visible is True
