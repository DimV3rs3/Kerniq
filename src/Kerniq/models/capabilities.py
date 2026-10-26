"""Remember which models cannot use native tool calls.

The file lives in the project state directory, next to settings. Uninstall
removes it with the rest of state/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_FILE = "model_capabilities.json"


def _path(state_dir: Optional[Path | str]) -> Optional[Path]:
    if not state_dir:
        return None
    return Path(state_dir) / _FILE


def _read(state_dir: Optional[Path | str]) -> dict:
    path = _path(state_dir)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def native_tools_enabled(state_dir: Optional[Path | str], model_id: str) -> bool:
    """Unknown models are assumed to support native tools."""
    model_id = (model_id or "").strip()
    if not model_id:
        return True
    row = _read(state_dir).get(model_id)
    if not isinstance(row, dict):
        return True
    return row.get("native_tools") is not False


def remember_native_tools(state_dir: Optional[Path | str], model_id: str, enabled: bool) -> None:
    model_id = (model_id or "").strip()
    path = _path(state_dir)
    if not model_id or path is None:
        return
    data = _read(state_dir)
    row = data.get(model_id)
    if not isinstance(row, dict):
        row = {}
    row["native_tools"] = bool(enabled)
    data[model_id] = row
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        return
