"""A private venv inside the workspace. Shell commands use it instead of the host Python."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

SANDBOX_NAME = ".kerniq-venv"
_prepared: set[str] = set()


def sandbox_python_path(workspace: Path) -> Path:
    root = Path(workspace).resolve()
    if os.name == "nt":
        return root / SANDBOX_NAME / "Scripts" / "python.exe"
    return root / SANDBOX_NAME / "bin" / "python"


def _has_pip(python: Path) -> bool:
    result = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.returncode == 0


def _bootstrap_pip(python: Path) -> None:
    if _has_pip(python):
        return
    subprocess.run(
        [str(python), "-m", "ensurepip", "--upgrade"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if _has_pip(python):
        return
    try:
        import urllib.request

        script = python.parent.parent / "get-pip.py"
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", script)
        subprocess.run([str(python), str(script)], capture_output=True, text=True, timeout=180, check=False)
    except Exception as exc:
        logger.warning("Could not install pip into the workspace sandbox: %s", exc)


def ensure_sandbox_python(workspace: Path) -> Path | None:
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    python = sandbox_python_path(root)
    if python.is_file() and _has_pip(python):
        return python
    dest = python.parent.parent
    logger.info("Creating workspace sandbox %s", dest)
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(dest)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if not python.is_file():
        subprocess.run(
            [sys.executable, "-m", "venv", "--without-pip", "--clear", str(dest)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    if not python.is_file():
        detail = ((result.stderr or "") + (result.stdout or ""))[-400:]
        logger.warning("Workspace sandbox was not created: %s", detail)
        return None
    _bootstrap_pip(python)
    return python


def _is_other_venv_bin(path: str, sandbox_bin: Path) -> bool:
    try:
        candidate = Path(path).resolve()
    except OSError:
        return False
    if candidate == sandbox_bin:
        return False
    if candidate.name.lower() not in {"scripts", "bin"}:
        return False
    return (candidate.parent / "pyvenv.cfg").is_file()


def apply_sandbox_env(env: dict, workspace: Path) -> dict:
    """Point python/pip at the workspace sandbox and hide any other venv on PATH."""
    python = ensure_sandbox_python(workspace)
    if python is None:
        return env
    out = dict(env)
    bindir = python.parent.resolve()
    out["VIRTUAL_ENV"] = str(bindir.parent)
    out.pop("PYTHONHOME", None)
    kept: list[str] = []
    for part in out.get("PATH", "").split(os.pathsep):
        if not part or _is_other_venv_bin(part, bindir):
            continue
        kept.append(part)
    out["PATH"] = os.pathsep.join([str(bindir), *kept])
    out["KERNIQ_SANDBOX"] = str(bindir.parent)
    key = str(Path(workspace).resolve())
    if key not in _prepared:
        _prepared.add(key)
        try:
            from Kerniq.sandbox.deps import ensure_project_deps

            ensure_project_deps(Path(workspace), str(python), enabled=True)
        except Exception as exc:
            logger.warning("Workspace dependency install failed: %s", exc)
    return out
