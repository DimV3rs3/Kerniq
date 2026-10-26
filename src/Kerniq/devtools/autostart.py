"""Start the Web UI in the background at the next sign-in.

Windows uses the Startup folder. Linux uses a systemd user service when
systemctl is available, and an XDG autostart entry otherwise. macOS uses a
LaunchAgent. Enabling does not start a second server. The entry runs at the
next sign-in. Pass ``invoke=False`` to write the files only.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from Kerniq.devtools.paths import find_project_root

_STATE = "autostart.json"
_UNIT = "kerniq-ui.service"
_DESKTOP = "kerniq-ui.desktop"
_PLIST = "com.kerniq.ui.plist"
_VBS = "Kerniq UI.vbs"


def _project(explicit: Path | None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    found = find_project_root()
    return found.resolve() if found is not None else Path.cwd().resolve()


def _home(explicit: Path | None) -> Path:
    return Path(explicit).expanduser().resolve() if explicit is not None else Path.home()


def _system(explicit: str | None) -> str:
    return explicit or platform.system()


def _python(project: Path, system: str) -> str:
    if system == "Windows":
        for candidate in (
            project / ".venv" / "Scripts" / "pythonw.exe",
            project / ".venv" / "Scripts" / "python.exe",
        ):
            if candidate.is_file():
                return str(candidate)
        return "pythonw"
    candidate = project / ".venv" / "bin" / "python"
    if candidate.is_file():
        return str(candidate)
    return "python3"


def _state_path(project: Path) -> Path:
    return project / "state" / _STATE


def _read_state(project: Path) -> dict[str, Any]:
    path = _state_path(project)
    if not path.is_file():
        return {"enabled": False}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"enabled": False}
    return data if isinstance(data, dict) else {"enabled": False}


def _write_state(project: Path, payload: dict[str, Any]) -> None:
    path = _state_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _targets(home: Path) -> dict[str, Path]:
    return {
        "startup": home / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / _VBS,
        "xdg": home / ".config" / "autostart" / _DESKTOP,
        "systemd": home / ".config" / "systemd" / "user" / _UNIT,
        "launchagent": home / "Library" / "LaunchAgents" / _PLIST,
    }


def _quote(value: str) -> str:
    return '"' + value.replace('"', "") + '"'


def _vbs(project: Path, python: str) -> str:
    command = f'""{python}"" -m Kerniq plugins ui'
    return (
        'Set sh = CreateObject("WScript.Shell")\r\n'
        f'sh.CurrentDirectory = "{project}"\r\n'
        f'sh.Run "{command}", 0, False\r\n'
    )


def _desktop(project: Path, python: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Kerniq UI\n"
        "Comment=Kerniq Web UI in the background\n"
        f"Exec={_quote(python)} -m Kerniq plugins ui\n"
        f"Path={project}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _unit(project: Path, python: str) -> str:
    return (
        "[Unit]\n"
        "Description=Kerniq Web UI\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"WorkingDirectory={project}\n"
        f"ExecStart={_quote(python)} -m Kerniq plugins ui\n"
        "Restart=on-failure\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _plist(project: Path, python: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.kerniq.ui</string>
  <key>WorkingDirectory</key>
  <string>{project}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>Kerniq</string>
    <string>plugins</string>
    <string>ui</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
</dict>
</plist>
"""


def _systemctl(*args: str) -> bool:
    if shutil.which("systemctl") is None:
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            check=False,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _clear(home: Path, *, invoke: bool) -> None:
    targets = _targets(home)
    if invoke and targets["systemd"].is_file():
        _systemctl("disable", _UNIT)
    for path in targets.values():
        if path.is_file():
            path.unlink()
    if invoke:
        _systemctl("daemon-reload")


def current(*, project: Path | None = None, home: Path | None = None, system: str | None = None) -> dict[str, Any]:
    root = _project(project)
    state = _read_state(root)
    enabled = bool(state.get("enabled"))
    method = str(state.get("method") or "")
    path = state.get("path") or ""
    present = bool(path) and Path(str(path)).is_file()
    if enabled and not present:
        enabled = False
    message = "Autostart is on. The Web UI starts in the background at the next sign-in." if enabled else "Autostart is off."
    return {
        "ok": True,
        "enabled": enabled,
        "method": method if enabled else "",
        "path": path if enabled else "",
        "system": _system(system),
        "message": message,
    }


def configure(
    enabled: bool,
    *,
    project: Path | None = None,
    home: Path | None = None,
    system: str | None = None,
    invoke: bool = True,
) -> dict[str, Any]:
    root = _project(project)
    folder = _home(home)
    host = _system(system)
    _clear(folder, invoke=invoke)
    if not enabled:
        _write_state(root, {"enabled": False, "system": host})
        return {
            "ok": True,
            "enabled": False,
            "method": "",
            "path": "",
            "system": host,
            "message": "Autostart is off. The sign-in entry was removed. This session was left as it is.",
        }
    python = _python(root, host)
    targets = _targets(folder)
    method = "xdg"
    path = targets["xdg"]
    body = _desktop(root, python)
    if host == "Windows":
        method, path, body = "startup", targets["startup"], _vbs(root, python)
    elif host == "Darwin":
        method, path, body = "launchagent", targets["launchagent"], _plist(root, python)
    elif host == "Linux" and invoke and shutil.which("systemctl"):
        method, path, body = "systemd", targets["systemd"], _unit(root, python)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    if method == "systemd":
        enabled_unit = _systemctl("daemon-reload") and _systemctl("enable", _UNIT)
        if not enabled_unit:
            path.unlink(missing_ok=True)
            method = "xdg"
            path = targets["xdg"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_desktop(root, python), encoding="utf-8")
    _write_state(root, {"enabled": True, "method": method, "path": str(path), "system": host, "project": str(root)})
    return {
        "ok": True,
        "enabled": True,
        "method": method,
        "path": str(path),
        "system": host,
        "message": (
            "The Web UI will start in the background the next time you sign in. "
            "This session was not started again."
        ),
    }
