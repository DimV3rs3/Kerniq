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


def _project_root_of(path: Path) -> Path | None:
    cur = path.resolve()
    for _ in range(8):
        if (cur / "pyproject.toml").is_file() and (cur / "src" / "Kerniq").is_dir():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def sandbox_workspace(workspace: Path) -> Path | None:
    """The private venv lives in the configured workspace, never in the install tree.

    ``<project>/workspace`` is allowed. ``<project>``, ``src``, and ``plugins`` are not.
    """
    root = Path(workspace).resolve()
    project = _project_root_of(root)
    if project is None:
        return root
    allowed = (project / "workspace").resolve()
    try:
        root.relative_to(allowed)
    except ValueError:
        logger.warning(
            "Refusing to create a sandbox in the Kerniq install tree (%s). Use the workspace folder.",
            root,
        )
        return None
    return root


def _venv_site(python: Path) -> Path:
    """site-packages of this venv, asked from that interpreter when it runs."""
    result = hidden_run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = (result.stdout or "").strip()
    if result.returncode == 0 and text:
        return Path(text)
    if os.name == "nt":
        return python.parent.parent / "Lib" / "site-packages"
    return (
        python.parent.parent
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


def _bootstrap_pip(python: Path) -> None:
    """Give the sandbox a pip. Debian often disables ensurepip."""
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
    site = _venv_site(python)
    try:
        site.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Workspace sandbox has no pip. %s", exc)
        return
    logger.info("ensurepip did not install pip. Using the host pip instead.")
    hidden_run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--target",
            str(site),
            "pip",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if not _has_pip(python):
        logger.warning(
            "Workspace sandbox has no pip. ensurepip failed, and the host pip could not install it."
        )


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
    root = sandbox_workspace(workspace)
    if root is None:
        return None
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


def install_guard(python: Path) -> None:
    """Install the process guard into the venv so scripts cannot call host programs."""
    from Kerniq.sandbox.guard import sitecustomize_source

    if os.name == "nt":
        site = python.parent.parent / "Lib" / "site-packages"
    else:
        site = (
            python.parent.parent
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )
    try:
        site.mkdir(parents=True, exist_ok=True)
        dest = site / "sitecustomize.py"
        text = sitecustomize_source()
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            return
        dest.write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.warning("Sandbox guard was not installed: %s", exc)


def apply_sandbox_env(
    env: dict,
    workspace: Path,
    *,
    external_roots: list | None = None,
    confine: bool = True,
    visible_roots: list | None = None,
) -> dict:
    """Point python/pip at the workspace sandbox and hide the computer's PATH.

    The shell can use the private venv. It cannot see dotnet, node, cmd, or
    anything else installed on the machine. ``external_roots`` are attached
    folders the script may read but must not modify. When ``confine`` is set,
    Python itself may not open paths outside ``visible_roots``.
    """
    python = ensure_sandbox_python(workspace)
    out = dict(env)
    if python is None:
        _install_loose_guard(workspace)
        guard = Path(workspace) / ".kerniq-guard"
        if (guard / "sitecustomize.py").is_file():
            out["PYTHONPATH"] = str(guard.resolve())
            out.pop("PYTHONSAFEPATH", None)
            out["PYTHONNOUSERSITE"] = "1"
    else:
        install_guard(python)
        bindir = python.parent.resolve()
        venv_root = bindir.parent
        out["VIRTUAL_ENV"] = str(venv_root)
        out.pop("PYTHONHOME", None)
        parts = [str(bindir)]
        if os.name == "nt":
            parts.append(str(venv_root))
        out["PATH"] = os.pathsep.join(parts)
        out["PYTHONNOUSERSITE"] = "1"
        out["PYTHONSAFEPATH"] = "1"
        out.pop("PYTHONPATH", None)
        out.pop("PYTHONSTARTUP", None)
        out["KERNIQ_SANDBOX"] = str(venv_root)
    roots = [str(item) for item in (external_roots or []) if str(item).strip()]
    if roots:
        out["KERNIQ_EXTERNAL_RO"] = os.pathsep.join(roots)
    else:
        out.pop("KERNIQ_EXTERNAL_RO", None)
    if confine:
        visible = []
        for item in list(visible_roots or []) + [workspace]:
            text = str(item or "").strip()
            if text and text not in visible:
                visible.append(text)
        out["KERNIQ_CONFINE"] = "1"
        out["KERNIQ_VISIBLE"] = os.pathsep.join(visible)
    else:
        out.pop("KERNIQ_CONFINE", None)
        out.pop("KERNIQ_VISIBLE", None)
    return out


def _install_loose_guard(workspace: Path) -> None:
    """Drop a sitecustomize next to the workspace when no venv could be built."""
    from Kerniq.sandbox.guard import sitecustomize_source

    guard = Path(workspace) / ".kerniq-guard"
    try:
        guard.mkdir(parents=True, exist_ok=True)
        dest = guard / "sitecustomize.py"
        text = sitecustomize_source()
        if dest.is_file() and dest.read_text(encoding="utf-8") == text:
            return
        dest.write_text(text, encoding="utf-8")
    except OSError as exc:
        logger.warning("Python guard was not installed: %s", exc)

