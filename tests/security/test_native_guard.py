"""Host escapes that go around builtins.open: ctypes, os.open, UNC, settings."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from Kerniq.models.providers.lm_studio import _AUTH_FAILS, _AUTH_LIMIT, _audit_lm_response, lm_auth_limited
from Kerniq.sandbox.guard import confine_allows, native_dll_blocked, sitecustomize_source
from Kerniq.settings.ui_store import UiSettingsStore


_CONFINE = {"KERNIQ_CONFINE": "1", "KERNIQ_VISIBLE": "/tmp/workspace-only"}


def test_unc_and_native_libraries_are_refused_without_a_syscall():
    assert confine_allows(r"\\localhost\D$", environ=_CONFINE) is False
    assert confine_allows("//server/share/marker.txt", environ=_CONFINE) is False
    assert confine_allows(r"\\?\C:\Windows\win.ini", environ=_CONFINE) is False
    assert native_dll_blocked(None, environ=_CONFINE) is True
    assert native_dll_blocked("kernel32", environ=_CONFINE) is True
    assert native_dll_blocked(r"C:\Windows\System32\ntdll.dll", environ=_CONFINE) is True
    assert native_dll_blocked("libc.so.6", environ=_CONFINE) is True
    assert native_dll_blocked("libpython3.11.so.1.0", environ=_CONFINE) is False
    assert native_dll_blocked("kernel32", environ={"KERNIQ_CONFINE": "0"}) is False


def test_confined_script_cannot_leave_or_disable_the_guard(tmp_path: Path):
    visible = tmp_path / "workspace"
    visible.mkdir()
    (visible / "ok.txt").write_text("hello", encoding="utf-8")
    script = visible / "check.py"
    script.write_text(
        sitecustomize_source()
        + "\n"
        + f"VISIBLE = {str(visible)!r}\n"
        + r"""
import os, pathlib, sys
os.environ["KERNIQ_CONFINE"] = "0"
os.environ["KERNIQ_VISIBLE"] = "/"
os.environ["KERNIQ_SANDBOX"] = "/usr"
def blocked(fn):
    try:
        fn()
    except (PermissionError, FileNotFoundError):
        return True
    return False
assert blocked(lambda: open("/etc/passwd"))
assert blocked(lambda: os.open("/etc/passwd", os.O_RDONLY))
assert pathlib.Path("/etc/passwd").exists() is False
assert pathlib.Path("//localhost/share").exists() is False
assert blocked(lambda: pathlib.Path("/etc/passwd").read_text())
import io
assert blocked(lambda: io.FileIO("/etc/passwd", "r"))
import ctypes
assert blocked(lambda: ctypes.CDLL(None))
assert blocked(lambda: ctypes.CDLL("libc.so.6"))
import socket
def connect():
    sock = socket.socket()
    sock.settimeout(0.2)
    sock.connect(("127.0.0.1", 1234))
assert blocked(connect)
target = pathlib.Path(VISIBLE) / "out.txt"
target.write_text("inside", encoding="utf-8")
assert target.read_text() == "inside"
assert not hasattr(sys.modules["__main__"], "_ORIG_OPEN")
"""
        ,
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["KERNIQ_CONFINE"] = "1"
    env["KERNIQ_VISIBLE"] = str(visible)
    env["KERNIQ_SANDBOX"] = str(visible / ".kerniq-venv")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(visible),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_unsigned_host_freedom_is_ignored_and_backup_is_removed(tmp_path: Path):
    state = tmp_path / "state"
    state.mkdir()
    (state / "settings.json").write_text(
        json.dumps(
            {
                "agent": {
                    "host_freedom": True,
                    "allow_elevated": True,
                    "use_venv": False,
                    "workspace": "D:/work",
                }
            }
        ),
        encoding="utf-8",
    )
    (state / "settings.json.backup").write_text(
        json.dumps({"agent": {"host_freedom": True}}),
        encoding="utf-8",
    )
    loaded = UiSettingsStore(state).load()
    assert loaded.agent.host_freedom is False
    assert loaded.agent.allow_elevated is False
    assert loaded.agent.use_venv is True
    assert loaded.agent.workspace == "D:/work"
    assert not (state / "settings.json.backup").exists()


def test_signed_host_freedom_stays_until_the_file_is_tampered(tmp_path: Path):
    store = UiSettingsStore(tmp_path)
    store.load()
    store.update({"agent": {"host_freedom": True, "workspace": "/data/proj"}})
    assert UiSettingsStore(tmp_path).load().agent.host_freedom is True
    path = tmp_path / "settings.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["agent"]["workspace"] = "C:/Windows"
    path.write_text(json.dumps(data), encoding="utf-8")
    fresh = UiSettingsStore(tmp_path).load()
    assert fresh.agent.host_freedom is False
    assert fresh.agent.workspace == "./workspace"


def test_lm_studio_auth_failures_pause_without_recording_the_token():
    _AUTH_FAILS["start"] = 0
    _AUTH_FAILS["count"] = 0

    class _Response:
        status_code = 401

        class request:
            url = "http://127.0.0.1:1234/v1/models?token=secret"

    import asyncio

    for _ in range(_AUTH_LIMIT):
        asyncio.run(_audit_lm_response(_Response()))
    assert lm_auth_limited() is True
    _AUTH_FAILS["start"] = 0
    _AUTH_FAILS["count"] = 0
