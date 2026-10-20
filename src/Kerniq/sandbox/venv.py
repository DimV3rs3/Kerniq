"""A private venv inside the workspace. Shell commands use it instead of the host Python."""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

from Kerniq.sandbox.proc import hidden_run

logger = logging.getLogger(__name__)

SANDBOX_NAME = ".kerniq-venv"


def sandbox_python_path(workspace: Path) -> Path:
    root = Path(workspace).resolve()
    if os.name == "nt":
        return root / SANDBOX_NAME / "Scripts" / "python.exe"
    return root / SANDBOX_NAME / "bin" / "python"


def _has_pip(python: Path) -> bool:
    result = hidden_run(
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
    hidden_run(
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
        hidden_run([str(python), str(script)], capture_output=True, text=True, timeout=180, check=False)
    except Exception as exc:
        logger.warning("Could not install pip into the workspace sandbox: %s", exc)


def _python_runs(python: Path) -> bool:
    if not python.is_file():
        return False
    result = hidden_run(
        [str(python), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0


def ensure_sandbox_python(workspace: Path) -> Path | None:
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    python = sandbox_python_path(root)
    if _python_runs(python) and _has_pip(python):
        return python
    dest = python.parent.parent
    if dest.exists():
        logger.info("Recreating broken workspace sandbox %s", dest)
        shutil.rmtree(dest, ignore_errors=True)
    logger.info("Creating workspace sandbox %s", dest)
    result = hidden_run(
        [sys.executable, "-m", "venv", str(dest)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if not python.is_file():
        hidden_run(
            [sys.executable, "-m", "venv", "--without-pip", "--clear", str(dest)],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    if not _python_runs(python):
        detail = ((result.stderr or "") + (result.stdout or ""))[-400:]
        logger.warning("Workspace sandbox was not created: %s", detail)
        return None
    _bootstrap_pip(python)
    return python if _python_runs(python) else None


def prepare_workspace_at_install(project: Path) -> None:
    """Create the workspace sandbox once, from the installer console."""
    workspace = Path(project) / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    python = ensure_sandbox_python(workspace)
    if python is None:
        raise SystemExit("workspace sandbox was not created")
    from Kerniq.sandbox.deps import ensure_project_deps

    ensure_project_deps(workspace, str(python), enabled=True)


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
    return out
