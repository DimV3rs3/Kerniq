"""Per-tool and per-plugin values.

Tools: state/tools.json under ``components``.
Plugins: state/plugins.json under ``components``.

Validation adds a missing component with its schema defaults. Removing a
component from disk drops its block on the next validation. User values
already stored for a live component are kept. The main settings file is
not used here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from ..interfaces.settings_schema import SettingsSchema, coerce_value
from .file import PLUGINS_FILE, TOOLS_FILE, read_state_file, write_state_file


class ComponentSettingsStore:
    def __init__(self, state_dir: Path | str):
        from .file import state_root

        self.root = state_root(state_dir)

    def _name(self, kind: str) -> str:
        return PLUGINS_FILE if kind == "plugin" else TOOLS_FILE

    def _read(self, kind: str) -> dict:
        data = read_state_file(self.root, self._name(kind))
        return data if isinstance(data, dict) else {}

    def _write(self, kind: str, raw: dict) -> None:
        write_state_file(self.root, self._name(kind), raw)

    def _bucket(self, raw: dict) -> dict:
        bucket = raw.get("components")
        if not isinstance(bucket, dict):
            bucket = {}
            raw["components"] = bucket
        return bucket

    def load(self, kind: str, component_id: str, schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        data = self._bucket(self._read(kind)).get(component_id) or {}
        if not isinstance(data, dict):
            data = {}
        if schema:
            merged = schema.defaults()
            for field in schema.fields:
                if field.key in data:
                    merged[field.key] = coerce_value(field, data[field.key])
            return merged
        return dict(data)

    def save(self, kind: str, component_id: str, values: Dict[str, Any], schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        if schema:
            clean: Dict[str, Any] = {}
            for field in schema.fields:
                if field.key in values:
                    clean[field.key] = coerce_value(field, values[field.key])
                else:
                    clean[field.key] = field.default
            values = clean
        raw = self._read(kind)
        self._bucket(raw)[component_id] = values
        self._write(kind, raw)
        return values

    def reconcile(self, kind: str, schemas: Dict[str, Optional[SettingsSchema]]) -> None:
        """Add defaults for new ids and delete settings for ids that are gone."""
        raw = self._read(kind)
        bucket = self._bucket(raw)
        live = set(schemas)
        for component_id in list(bucket):
            if component_id not in live:
                del bucket[component_id]
        for component_id, schema in schemas.items():
            current = bucket.get(component_id)
            if not isinstance(current, dict):
                current = {}
            if schema is None or not schema.fields:
                bucket[component_id] = current
                continue
            merged = schema.defaults()
            for field in schema.fields:
                if field.key in current:
                    merged[field.key] = coerce_value(field, current[field.key])
            bucket[component_id] = merged
        self._write(kind, raw)

    def reset(self, kind: str, component_id: str, schema: Optional[SettingsSchema] = None) -> Dict[str, Any]:
        raw = self._read(kind)
        self._bucket(raw).pop(component_id, None)
        self._write(kind, raw)
        if schema:
            return self.save(kind, component_id, schema.defaults(), schema)
        return {}

    def reset_all(self) -> int:
        n = 0
        for kind in ("tool", "plugin"):
            raw = self._read(kind)
            bucket = raw.get("components") if isinstance(raw.get("components"), dict) else {}
            n += len(bucket)
            raw["components"] = {}
            self._write(kind, raw)
        return n

    def forget(self, kind: str, *component_ids: str) -> None:
        """Drop settings for components that were removed from disk."""
        raw = self._read(kind)
        bucket = self._bucket(raw)
        changed = False
        for component_id in component_ids:
            if component_id and component_id in bucket:
                del bucket[component_id]
                changed = True
        if changed:
            self._write(kind, raw)
