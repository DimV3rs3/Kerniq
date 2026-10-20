"""Uninstall Kerniq package and optional local state.

On Windows, `kerniq.exe` cannot delete itself while this process is still
running from that executable. In that case we re-launch the uninstall via
`python -m Kerniq uninstall --deferred ...` and exit the parent so the lock
is released.
"""

from __future__ import annotations

import json
import os
import shutil
import site
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


def _run(cmd: List[str], timeout: int = 180) -> Tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out
    except Exception as e:
        return 1, str(e)


def _is_running_as_kerniq_exe() -> bool:
    """True when argv[0] is the console-script wrapper we need to delete."""
    try:
        arg0 = Path(sys.argv[0]).resolve()
    except Exception:
        arg0 = Path(sys.argv[0])
    name = arg0.name.lower()
    if name in ("kerniq.exe", "kerniq", "kerniq-script.py"):
        return True
    # Frozen / launcher variants
    if "scripts" in str(arg0).lower() and "kerniq" in name:
        return True
    return False


def _script_dirs() -> List[Path]:
    dirs: List[Path] = []
    try:
        user_base = site.getuserbase()
        if user_base:
            dirs.append(Path(user_base) / "Scripts")
            dirs.append(Path(user_base) / "bin")
    except Exception:
        pass
    prefix = Path(sys.prefix)
    dirs.append(prefix / "Scripts")
    dirs.append(prefix / "bin")
    try:
        dirs.append(Path(site.getusersitepackages()).parent.parent / "Scripts")
    except Exception:
        pass
    for part in os.environ.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        low = part.lower()
        if "scripts" in low or part.rstrip("\\/").endswith("bin"):
            dirs.append(Path(part))
    seen: set[str] = set()
    out: List[Path] = []
    for d in dirs:
        try:
            key = str(d.resolve())
        except Exception:
            key = str(d)
        if key in seen:
            continue
        seen.add(key)
        if d.is_dir():
            out.append(d)
    return out


def _unlink_with_retry(path: Path, attempts: int = 15, delay: float = 0.4) -> str:
    last_err: Optional[BaseException] = None
    for i in range(attempts):
        try:
            if not path.exists():
                return f"{path} (already gone)"
            path.unlink()
            return str(path)
        except OSError as e:
            last_err = e
            # Windows: file in use — wait and retry
            time.sleep(delay * (1.0 + i * 0.15))
    return f"{path} (failed: {last_err})"


def _remove_console_scripts() -> List[str]:
    removed: List[str] = []
    names = (
        "kerniq",
        "kerniq.exe",
        "kerniq-script.py",
        "Kerniq.exe",
        "kerniq-script.pyw",
    )
    for d in _script_dirs():
        for name in names:
            p = d / name
            if p.is_file() or p.is_symlink():
                removed.append(_unlink_with_retry(p))
    return removed


def _project_workspace(project_root: Path) -> Optional[Path]:
    """In-project workspace to drop. Never the project root, source, or an external path."""
    raw = "./workspace"
    settings = project_root / "state" / "settings.json"
    if settings.is_file():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
            agent = data.get("agent") if isinstance(data, dict) else None
            if isinstance(agent, dict) and agent.get("workspace"):
                raw = str(agent.get("workspace"))
        except Exception:
            raw = "./workspace"
    path = Path(raw)
    if not path.is_absolute():
        path = project_root / path
    try:
        path = path.resolve()
        rel = path.relative_to(project_root.resolve())
    except Exception:
        return None
    if not rel.parts:
        return None
    if rel.parts[0] in {"src", "plugins", "tests", "config", ".git"}:
        return None
    return path


def _purge_project_state(project_root: Path) -> List[str]:
    cleaned: List[str] = []
    extra = _project_workspace(project_root)
    targets = [
        project_root / name
        for name in (
            "sessions",
            "logs",
            "state",
            "workspace",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
        )
    ]
    if extra is not None:
        targets.append(extra)
    seen: set[str] = set()
    for p in targets:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key in seen:
            continue
        seen.add(key)
        if not p.is_dir():
            continue
        # Never delete a Python package. User data dirs have no __init__.py.
        if (p / "__init__.py").is_file():
            cleaned.append(f"{p} (kept: python package)")
            continue
        try:
            rel = p.resolve().relative_to(project_root.resolve())
        except Exception:
            cleaned.append(f"{p} (kept: outside the project)")
            continue
        if not rel.parts or "src" in rel.parts:
            cleaned.append(f"{p} (kept: inside src)")
            continue
        try:
            shutil.rmtree(p, ignore_errors=True)
            cleaned.append(str(p))
        except Exception as e:
            cleaned.append(f"{p} (failed: {e})")
    for p in project_root.rglob("__pycache__"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            cleaned.append(str(p))
    return cleaned


def _spawn_deferred(purge: bool, wipe_project: bool = False) -> int:
    """Re-launch uninstall via python -m so kerniq.exe is not locked."""
    args = [
        sys.executable,
        "-m",
        "Kerniq",
        "uninstall",
        "--yes",
        "--deferred",
    ]
    if purge:
        args.append("--purge")
    if wipe_project:
        args.append("--wipe-project")

    print(
        "Running from kerniq.exe — cannot delete it while it is locked.\n"
        "Starting deferred uninstall via:\n"
        f"  {' '.join(args)}\n"
        "This window will exit; cleanup continues in the background."
    )

    # Detached process on Windows so it survives parent exit
    popen_kwargs: dict = {}
    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        popen_kwargs["creationflags"] = (
            CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS | CREATE_NO_WINDOW
        )
        # inherit nothing critical; write log next to temp
        log_path = Path(os.environ.get("TEMP", ".")) / "kerniq-uninstall.log"
        try:
            log_f = open(log_path, "w", encoding="utf-8")
            popen_kwargs["stdout"] = log_f
            popen_kwargs["stderr"] = subprocess.STDOUT
            print(f"Deferred log: {log_path}")
        except Exception:
            pass
    else:
        popen_kwargs["start_new_session"] = True

    try:
        subprocess.Popen(args, close_fds=True, **popen_kwargs)
    except Exception as e:
        print(f"Failed to spawn deferred uninstall: {e}", file=sys.stderr)
        print(
            "Run manually after closing this terminal:\n"
            f'  "{sys.executable}" -m Kerniq uninstall -y'
            + (" --purge" if purge else ""),
            file=sys.stderr,
        )
        return 1
    return 0


def _do_uninstall(*, purge: bool = False, wipe_project: bool = False) -> int:
    """Actual uninstall body (must not hold a lock on kerniq.exe)."""
    print(f"Python: {sys.executable}")
    if "--deferred" in sys.argv or os.environ.get("KERNIQ_UNINSTALL_DEFERRED") == "1":
        time.sleep(1.2)

    # Settings and runtime dirs go first, while this package can still be imported.
    # The source tree is left in place unless --wipe-project is set.
    if not wipe_project:
        _reset_user_state()

    print("Running: python -m pip uninstall Kerniq -y")
    code, out = _run([sys.executable, "-m", "pip", "uninstall", "Kerniq", "-y"])
    if out:
        print(out)
    # Retry pip once if WinError 32
    if code != 0 and ("WinError 32" in out or "being used by another process" in out.lower()):
        print("pip hit a locked file — waiting and retrying…")
        time.sleep(2.0)
        code, out = _run([sys.executable, "-m", "pip", "uninstall", "Kerniq", "-y"])
        if out:
            print(out)
    _run([sys.executable, "-m", "pip", "uninstall", "kerniq", "-y"])

    # Always try to clean leftover scripts (with retries)
    removed = _remove_console_scripts()
    if removed:
        print("Console scripts:")
        for r in removed:
            print(f"  - {r}")
    else:
        print("No leftover kerniq scripts found in known Scripts/bin dirs.")

    if purge:
        try:
            from Kerniq.devtools.paths import find_project_root

            root = find_project_root()
        except Exception:
            root = None
        if root is None:
            cwd = Path.cwd()
            if (cwd / "pyproject.toml").is_file():
                root = cwd
        if root:
            print(f"Purging local state under {root}")
            for p in _purge_project_state(root):
                print(f"  - {p}")
        else:
            print("Could not detect project root; skipped --purge.")

    if wipe_project:
        print()
        print("=== WIPE PROJECT (irreversible) ===")
        roots = _find_install_roots()
        if not roots:
            print("No Kerniq project root found to wipe.")
            print("Set KERNIQ_ROOT to the folder if needed.")
        else:
            for line in _wipe_project_trees(roots):
                print(line)
        # After wiping source, package import may be gone — still finish script cleanup
        print("Project tree wipe requested; source folders above were targeted.")

    print()
    if wipe_project:
        print("Done. Kerniq package and project files removed.")
        print("Nothing left to reinstall unless you restore from backup/git.")
    else:
        print("Done. To install again from a (possibly moved) source tree:")

    print("  cd <path-to-Kerniq>")
    print('  python -m pip install -e ".[dev,mcp]"')
    print('  or:  python -m Kerniq --version')
    # Success if scripts are gone even when first pip failed mid-way
    still = []
    for d in _script_dirs():
        for name in ("kerniq.exe", "kerniq", "Kerniq.exe"):
            if (d / name).is_file():
                still.append(str(d / name))
    if still:
        print("WARNING: still locked / present:")
        for s in still:
            print(f"  - {s}")
        print("Close any terminal still running kerniq, then:")
        print(f'  "{sys.executable}" -m Kerniq uninstall -y')
        return 1
    return 0 if code == 0 else 0  # package often already gone after partial uninstall


def _project_root() -> Optional[Path]:
    try:
        from Kerniq.devtools.paths import find_project_root
        root = find_project_root()
    except Exception:
        root = None
    if root is None:
        cwd = Path.cwd()
        if (cwd / "pyproject.toml").is_file():
            root = cwd
    return root


def _reset_user_state() -> None:
    """Drop settings and runtime directories. Leave the installed source tree."""
    root = _project_root()
    if root is None:
        print("Could not detect project root; user settings were not reset.")
        return
    print(f"Resetting user settings and runtime data under {root}")
    for line in _purge_project_state(root):
        print(f"  - {line}")
    home = Path.home() / ".kerniq"
    if home.is_dir():
        shutil.rmtree(home, ignore_errors=True)
        print(f"  - {home}")


def _find_install_roots() -> List[Path]:
    """Locate Kerniq source trees we are allowed to wipe."""
    roots: List[Path] = []
    seen: set[str] = set()

    def add(p: Optional[Path]) -> None:
        if p is None:
            return
        try:
            p = p.resolve()
        except Exception:
            return
        if not p.is_dir():
            return
        key = str(p)
        if key in seen:
            return
        # Must look like Kerniq project
        if not (p / "pyproject.toml").is_file():
            return
        try:
            text = (p / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return
        if "name = \"Kerniq\"" not in text and 'name = "Kerniq"' not in text:
            if "Kerniq" not in text:
                return
        seen.add(key)
        roots.append(p)

    # Env override
    for key in ("KERNIQ_ROOT", "KERNIQ_HOME"):
        val = os.environ.get(key)
        if val:
            add(Path(val).expanduser())

    try:
        from Kerniq.devtools.paths import find_project_root
        add(find_project_root())
    except Exception:
        pass

    # Package location: .../src/Kerniq/__init__.py -> repo root
    try:
        import Kerniq as _pkg
        pkg = Path(getattr(_pkg, "__file__", "") or "")
        if pkg.is_file():
            # src layout: repo/src/Kerniq/__init__.py
            for up in (2, 3, 1):
                if len(pkg.parents) > up:
                    add(pkg.parents[up])
    except Exception:
        pass

    add(Path.cwd())
    return roots


def _wipe_project_trees(roots: List[Path]) -> List[str]:
    """Recursively delete entire project directories. Irreversible."""
    report: List[str] = []
    for root in roots:
        report.append(f"WIPING: {root}")
        try:
            # On Windows, retry a few times for locked files
            for attempt in range(5):
                try:
                    shutil.rmtree(root)
                    report.append(f"  deleted {root}")
                    break
                except OSError as e:
                    if attempt >= 4:
                        report.append(f"  FAILED {root}: {e}")
                    else:
                        time.sleep(0.6)
        except Exception as e:
            report.append(f"  FAILED {root}: {e}")
    return report


def uninstall(
    *,
    purge: bool = False,
    wipe_project: bool = False,
    yes: bool = False,
    deferred: bool = False,
) -> int:
    """
    Uninstall Kerniq from the current Python environment.

    Does NOT delete the source tree. User settings, sessions, logs, and state
    are removed so the next install starts from defaults. --wipe-project deletes
    the source tree as well.
    """
    if not yes and not deferred:
        print(
            "This will uninstall the Kerniq package from this Python environment\n"
            f"  python: {sys.executable}\n"
            "and remove the `kerniq` console script if present.\n"
            "Pass --yes to confirm.\n\n"
            "Tip (Windows): if `kerniq remove` fails with WinError 32, run:\n"
            f'  "{sys.executable}" -m Kerniq uninstall -y'
        )
        return 2

    # When invoked as kerniq.exe, hand off to python -m and exit
    if not deferred and _is_running_as_kerniq_exe():
        return _spawn_deferred(purge=purge, wipe_project=wipe_project)

    return _do_uninstall(purge=purge, wipe_project=wipe_project)
