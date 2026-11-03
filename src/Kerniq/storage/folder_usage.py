"""Per-folder space that Kerniq itself added.

The baseline is the size of the folder the first time Kerniq measured it.
Files that were already there do not count. If the folder later shrinks
below that mark, the mark drops with it, so the used figure never goes
negative. Limits and baselines live under the home ``.kerniq`` directory,
not in the workspace, and file tools refuse that directory.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

DEFAULT_LIMIT = 4 * 1024 * 1024 * 1024
_PRIVATE_NAMES = {"folder_usage.json", "git_sessions.json", "kerniq_installed_git.json"}


def private_root() -> Path:
    return Path.home() / ".kerniq"


def usage_path() -> Path:
    return private_root() / "folder_usage.json"


def is_private_path(path: Path) -> bool:
    """True for Kerniq's own bookkeeping. The model must not read it."""
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved.name in _PRIVATE_NAMES:
        return True
    root = private_root()
    try:
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def measure(folder: Path) -> int:
    """Bytes on disk. Symlinks are not followed, so a view cannot double-count."""
    root = Path(folder)
    if not root.exists():
        return 0
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in {".kerniq-view", ".kerniq-venv"}]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or is_private_path(path):
                continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def _load(path: Path | None = None) -> dict:
    file = Path(path) if path is not None else usage_path()
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"folders": {}}
    if not isinstance(data, dict):
        return {"folders": {}}
    folders = data.get("folders")
    if not isinstance(folders, dict):
        data["folders"] = {}
    return data


def _save(data: dict, path: Path | None = None) -> None:
    file = Path(path) if path is not None else usage_path()
    file.parent.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(file.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, file)


def account(folder: Path, *, limit: int | None = None, store: Path | None = None) -> dict:
    """Return used bytes above the baseline. Used is never negative."""
    folder = Path(folder)
    try:
        key = str(folder.resolve())
    except OSError:
        key = str(folder)
    current = measure(folder)
    data = _load(store)
    row = data["folders"].get(key)
    if not isinstance(row, dict):
        row = {}
    if "baseline" not in row:
        baseline = current
    else:
        try:
            baseline = int(row.get("baseline") or 0)
        except (TypeError, ValueError):
            baseline = current
    if current < baseline:
        baseline = current
    if limit is None:
        try:
            limit = int(row.get("limit") or DEFAULT_LIMIT)
        except (TypeError, ValueError):
            limit = DEFAULT_LIMIT
    limit = max(1, int(limit))
    used = current - baseline
    if used < 0:
        used = 0
    row = {"baseline": baseline, "limit": limit, "current": current}
    data["folders"][key] = row
    _save(data, store)
    return {
        "path": key,
        "current": current,
        "baseline": baseline,
        "used": used,
        "limit": limit,
        "full": used >= limit,
    }


def set_limit(folder: Path, limit: int, *, store: Path | None = None) -> dict:
    return account(folder, limit=max(1, int(limit)), store=store)


def purge_older_than(folder: Path, days: int) -> int:
    """Delete files last touched more than ``days`` ago. Zero days deletes nothing."""
    if days <= 0:
        return 0
    root = Path(folder)
    if not root.is_dir():
        return 0
    cutoff = time.time() - (int(days) * 86400)
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in {".kerniq-view", ".kerniq-venv", ".git"}]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or is_private_path(path):
                continue
            try:
                if path.stat().st_mtime >= cutoff:
                    continue
                path.unlink()
                removed += 1
            except OSError:
                continue
    return removed


def parse_quota(amount, unit: str) -> int:
    """Megabytes or gigabytes to bytes. Empty means the 4 GiB default."""
    if amount is None or amount == "":
        return DEFAULT_LIMIT
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    if value < 0:
        value = 0
    scale = 1024 * 1024 * 1024 if str(unit or "gb").lower().startswith("g") else 1024 * 1024
    size = int(value * scale)
    return size if size > 0 else DEFAULT_LIMIT
