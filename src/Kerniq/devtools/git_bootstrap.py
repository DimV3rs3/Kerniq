"""Install git only when the machine does not have it, and remember that.

Uninstall removes git only when this marker says Kerniq installed it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


def marker_path(state_dir: Path | str) -> Path:
    return Path(state_dir) / "kerniq_installed_git.json"


def git_present() -> bool:
    return shutil.which("git") is not None


def read_marker(state_dir: Path | str) -> dict | None:
    path = marker_path(state_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _install_command() -> list[str] | None:
    if sys.platform.startswith("linux"):
        if shutil.which("apt-get"):
            return ["apt-get", "install", "-y", "git"]
        if shutil.which("dnf"):
            return ["dnf", "install", "-y", "git"]
    if sys.platform == "darwin" and shutil.which("brew"):
        return ["brew", "install", "git"]
    if sys.platform.startswith("win") and shutil.which("winget"):
        return ["winget", "install", "--id", "Git.Git", "-e", "--silent"]
    return None


def _remove_command() -> list[str] | None:
    if sys.platform.startswith("linux"):
        if shutil.which("apt-get"):
            return ["apt-get", "remove", "-y", "git"]
        if shutil.which("dnf"):
            return ["dnf", "remove", "-y", "git"]
    if sys.platform == "darwin" and shutil.which("brew"):
        return ["brew", "uninstall", "git"]
    if sys.platform.startswith("win") and shutil.which("winget"):
        return ["winget", "uninstall", "--id", "Git.Git", "-e", "--silent"]
    return None


def ensure_git(state_dir: Path | str) -> str:
    """Return present, installed, or missing. Never raises."""
    if git_present():
        return "present"
    command = _install_command()
    if not command:
        return "missing"
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return "missing"
    if proc.returncode != 0 or not git_present():
        return "missing"
    path = marker_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"installed_by_kerniq": True, "command": command[0]}),
        encoding="utf-8",
    )
    return "installed"


def remove_managed_git(state_dir: Path | str) -> str:
    """Remove git only when Kerniq installed it. The marker is read first."""
    data = read_marker(state_dir)
    if not data or not data.get("installed_by_kerniq"):
        return "left"
    command = _remove_command()
    if not command:
        return "left"
    try:
        subprocess.run(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return "failed"
    return "removed"
