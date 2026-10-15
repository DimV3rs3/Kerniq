"""Resolve project / plugins directories independent of current working directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional


def _has_plugins_tree(root: Path) -> bool:
    p = root / "plugins"
    return p.is_dir() and any(p.iterdir()) if p.exists() else False


def find_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start (or cwd) looking for a Kerniq project root."""
    cur = (start or Path.cwd()).resolve()
    for _ in range(12):
        if (cur / "pyproject.toml").is_file() and _has_plugins_tree(cur):
            return cur
        if (cur / "config" / "default.toml").is_file() and _has_plugins_tree(cur):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    env = os.environ.get("KERNIQ_ROOT") or os.environ.get("KERNIQ_HOME")
    if env:
        root = Path(env).expanduser().resolve()
        if root.is_dir():
            return root
    return None


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
