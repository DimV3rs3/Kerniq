"""Per-component settings files under state/ (tools/ and plugins/)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..interfaces.settings_schema import SettingsSchema, coerce_value


class ComponentSettingsStore:
    """One JSON file per component: state/{kind}/{component_id}.json"""

    def __init__(self, state_dir: Path | str):
        self.root = Path(state_dir)
        self.tools_dir = self.root / "tools"
        self.plugins_dir = self.root / "plugins"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, kind: str, component_id: str) -> Path:
        base = self.tools_dir if kind == "tool" else self.plugins_dir
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in component_id)
        return base / f"{safe}.json"

    def load(self, kind: str, component_id: str, schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        path = self._path(kind, component_id)
        data: Dict[str, Any] = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
        if schema:
            merged = schema.defaults()
            for f in schema.fields:
                if f.key in data:
                    merged[f.key] = coerce_value(f, data[f.key])
            return merged
        return data

    def save(self, kind: str, component_id: str, values: Dict[str, Any], schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        if schema:
            clean = {}
            for f in schema.fields:
                if f.key in values:
                    clean[f.key] = coerce_value(f, values[f.key])
                else:
                    clean[f.key] = f.default
            values = clean
        path = self._path(kind, component_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return values

    def reset(self, kind: str, component_id: str, schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        path = self._path(kind, component_id)
        if path.exists():
            path.unlink()
        if schema:
            return self.save(kind, component_id, schema.defaults(), schema)
        return {}

    def reset_all(self) -> int:
        n = 0
        for d in (self.tools_dir, self.plugins_dir):
            for f in d.glob("*.json"):
                f.unlink()
                n += 1
        return n
