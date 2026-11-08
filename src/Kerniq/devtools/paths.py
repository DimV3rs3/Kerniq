"""Resolve project / plugins directories independent of current working directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional


def _has_plugins_tree(root: Path) -> bool:
    p = root / "plugins"
    return p.is_dir() and any(p.iterdir()) if p.exists() else False


def _is_project_root(cur: Path) -> bool:
    try:
        if (cur / "pyproject.toml").is_file() and _has_plugins_tree(cur):
            return True
        if (cur / "config" / "default.toml").is_file() and _has_plugins_tree(cur):
            return True
    except OSError:
        return False
    return False


def _walk_for_root(start: Path) -> Optional[Path]:
    try:
        cur = Path(start).expanduser().resolve()
    except OSError:
        return None
    if cur.is_file():
        cur = cur.parent
    for _ in range(16):
        if _is_project_root(cur):
            return cur
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None


def _install_seeds() -> List[Path]:
    """Places this running Kerniq can be found, ignoring the shell cwd."""
    seeds: List[Path] = [Path(__file__).resolve()]
    argv0 = sys.argv[0] if sys.argv else ""
    if argv0 and argv0 not in {"-c", "-m"}:
        try:
            script = Path(argv0).expanduser()
            if script.exists():
                seeds.append(script)
        except OSError:
            pass
    for entry in sys.path[:24]:
        if not entry or entry == ".":
            continue
        try:
            seeds.append(Path(entry).expanduser())
        except Exception:
            continue
    return seeds


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Locate the Kerniq install, not the folder the shell happened to be in.

    Launching from ``C:\\Windows\\System32`` must still resolve to the
    directory that contains this package. A shell that is already inside an
    install (or ``scripts/``) keeps that install. ``KERNIQ_ROOT`` /
    ``KERNIQ_HOME`` override only when the cwd is not itself an install.
    """
    if start is not None:
        found = _walk_for_root(Path(start))
        if found is not None:
            return found

    found = _walk_for_root(Path.cwd())
    if found is not None:
        return found

    env = (os.environ.get("KERNIQ_ROOT") or os.environ.get("KERNIQ_HOME") or "").strip()
    if env:
        try:
            root = Path(env).expanduser().resolve()
        except OSError:
            root = None
        if root is not None and root.is_dir():
            return _walk_for_root(root) or root

    seen: set[str] = set()
    for seed in _install_seeds():
        try:
            key = str(seed.resolve())
        except OSError:
            key = str(seed)
        if key in seen:
            continue
        seen.add(key)
        found = _walk_for_root(seed)
        if found is not None:
            return found
    return None


def anchored_dir(path: object) -> Path:
    """Resolve a storage path from the project root, not from a random cwd.

    ``./sessions`` must stay ``<repo>/sessions``. It must not land inside
    ``src/Kerniq``, where it would overwrite the code package.
    """
    raw = Path(path)
    if raw.is_absolute():
        return raw
    root = find_project_root()
    if root is None:
        try:
            import Kerniq as pkg

            pkg_file = Path(getattr(pkg, "__file__", "") or "")
            if pkg_file.is_file() and len(pkg_file.parents) > 2:
                candidate = pkg_file.parents[2]
                if (candidate / "pyproject.toml").is_file():
                    root = candidate
        except Exception:
            root = None
    base = root or Path.cwd()
    return (base / raw).resolve()


def pin_process_root() -> Optional[Path]:
    """Move this process into the Kerniq install and export ``KERNIQ_ROOT``.

    ``./state``, ``./sessions``, and ``./workspace`` belong to that install.
    They must not be created beside ``scripts/`` or in the shell's cwd
    (``C:\\Windows\\System32`` included).
    """
    root = find_project_root()
    if root is None:
        return None
    root = root.resolve()
    os.environ["KERNIQ_ROOT"] = str(root)
    try:
        if Path.cwd().resolve() != root:
            os.chdir(root)
    except OSError:
        pass
    return root


def find_plugins_dirs() -> List[Path]:
    """Candidate plugin directories (first existing wins for discovery order)."""
    seen: set[str] = set()
    out: List[Path] = []

    def add(p: Path) -> None:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key in seen:
            return
        seen.add(key)
        if p.is_dir():
            out.append(p)

    # 1) Explicit env
    for key in ("KERNIQ_PLUGINS", "KERNIQ_ROOT", "KERNIQ_HOME"):
        val = os.environ.get(key)
        if not val:
            continue
        base = Path(val).expanduser()
        if key == "KERNIQ_PLUGINS":
            add(base)
        else:
            add(base / "plugins")

    # 2) Project root near cwd
    root = find_project_root()
    if root:
        add(root / "plugins")

    # 3) CWD
    add(Path("plugins"))
    add(Path.cwd() / "plugins")

    # 4) Directory of the running script / site-packages sibling (editable install layout)
    #    E:\Kerniq\src\Kerniq\... → project is two parents up from package if src layout
    try:
        import Kerniq as _pkg

        pkg_file = Path(getattr(_pkg, "__file__", "") or "")
        if pkg_file.is_file():
            # .../src/Kerniq/__init__.py → parents[2] = repo root (src layout)
            for up in (2, 3, 1):
                cand = pkg_file.parents[up] / "plugins" if len(pkg_file.parents) > up else None
                if cand is not None:
                    add(cand)
            # Also plugins shipped next to package (if ever packaged that way)
            add(pkg_file.parent / "plugins")
    except Exception:
        pass

    # 5) sys.path entries that look like a project
    for entry in sys.path[:12]:
        if not entry or entry == ".":
            continue
        try:
            ep = Path(entry)
            if (ep / "plugins").is_dir():
                add(ep / "plugins")
            if ep.name == "src" and (ep.parent / "plugins").is_dir():
                add(ep.parent / "plugins")
        except Exception:
            continue

    return out