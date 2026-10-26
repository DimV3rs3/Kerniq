"""Set and check plugin settings from the console.

``-s name value`` refuses a value the schema does not accept. Defaults are
written and checked without waiting for someone to open the JSON file.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from typing import Any, Optional

from ..interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from ..settings.component_store import ComponentSettingsStore
from .fields import with_manager_fields
from .manager import normalize_manifest_data
from .manifest import PluginManifest


def validate_assignment(field: SettingField, raw: Any) -> tuple[bool, Any, str]:
    """Accept a console or file value, or explain why it is rejected."""
    if field.type == SettingType.BOOL:
        if isinstance(raw, bool):
            return True, raw, ""
        text = str(raw).strip().lower()
        if text not in {"1", "0", "true", "false", "yes", "no", "on", "off"}:
            return False, None, f"{field.key}: expected true or false, got {raw!r}"
        return True, text in {"1", "true", "yes", "on"}, ""
    if field.type == SettingType.INT:
        if isinstance(raw, bool) or (isinstance(raw, str) and not str(raw).strip()):
            return False, None, f"{field.key}: expected an integer"
        try:
            value = int(str(raw).strip())
        except (TypeError, ValueError):
            return False, None, f"{field.key}: expected an integer, got {raw!r}"
        if field.minimum is not None and value < int(field.minimum):
            return False, None, f"{field.key}: {value} is below {int(field.minimum)}"
        if field.maximum is not None and value > int(field.maximum):
            return False, None, f"{field.key}: {value} is above {int(field.maximum)}"
        return True, value, ""
    if field.type == SettingType.FLOAT:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return False, None, f"{field.key}: expected a number, got {raw!r}"
        if field.minimum is not None and value < float(field.minimum):
            return False, None, f"{field.key}: {value} is below {field.minimum}"
        if field.maximum is not None and value > float(field.maximum):
            return False, None, f"{field.key}: {value} is above {field.maximum}"
        return True, value, ""
    if field.type == SettingType.SELECT:
        value = str(raw)
        allowed = {str(item.get("value")) for item in (field.options or [])}
        if allowed and value not in allowed:
            choices = ", ".join(sorted(allowed))
            return False, None, f"{field.key}: {value!r} is not one of {choices}"
        return True, value, ""
    return True, str(raw), ""


def assign_settings(
    schema: SettingsSchema,
    current: dict[str, Any],
    pairs: list[tuple[str, str]],
) -> tuple[dict[str, Any], list[str]]:
    fields = {field.key: field for field in schema.fields}
    updated = dict(current)
    errors: list[str] = []
    for key, raw in pairs:
        field = fields.get(key)
        if field is None:
            errors.append(f"unknown setting {key}")
            continue
        ok, value, err = validate_assignment(field, raw)
        if not ok:
            errors.append(err)
            continue
        updated[key] = value
    return updated, errors


def repair_values(schema: SettingsSchema, stored: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fill missing defaults and replace values the schema rejects."""
    notes: list[str] = []
    clean: dict[str, Any] = {}
    stored = stored if isinstance(stored, dict) else {}
    label = schema.component_id
    for field in schema.fields:
        if field.key not in stored:
            clean[field.key] = field.default
            notes.append(f"{label}.{field.key}: missing, default {field.default!r} applied")
            continue
        ok, value, err = validate_assignment(field, stored[field.key])
        if not ok:
            clean[field.key] = field.default
            notes.append(f"{label}.{field.key}: {err}; default {field.default!r} applied")
            continue
        clean[field.key] = value
    return clean, notes


def collect_schemas(plugins_dirs: list[Path]) -> dict[str, SettingsSchema]:
    schemas: dict[str, SettingsSchema] = {}
    for root in plugins_dirs:
        if not root.is_dir():
            continue
        for item in sorted(root.iterdir()):
            manifest_path = item / "manifest.toml"
            main_py = item / "main.py"
            if not item.is_dir() or not manifest_path.is_file() or not main_py.is_file():
                continue
            try:
                with open(manifest_path, "rb") as handle:
                    raw = tomllib.load(handle)
                data = normalize_manifest_data(raw)
                manifest = PluginManifest(**data)
                module_name = "kerniq_schema_" + item.name
                spec = importlib.util.spec_from_file_location(module_name, main_py)
                if spec is None or spec.loader is None:
                    print(f"{item.name}: schema was not loaded")
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                cls = getattr(module, "PluginImpl", None)
                if cls is None:
                    continue
                inst = cls()
                getter = getattr(inst, "settings_schema", None)
                schema = getter() if callable(getter) else None
                schema = with_manager_fields(schema, manifest.plugin_id, manifest.name)
                schemas[manifest.plugin_id] = schema
            except Exception as exc:
                print(f"{item.name}: schema was not loaded ({exc.__class__.__name__}: {exc})")
    return schemas


def validate_installed_defaults(
    state_dir: Path | str | None = None,
    plugins_dirs: Optional[list[Path]] = None,
) -> int:
    """Write missing defaults and repair invalid stored values. Does not start plugins."""
    from ..devtools.paths import anchored_dir, find_plugins_dirs
    from ..settings.loader import SettingsProvider

    if state_dir is None:
        state_dir = SettingsProvider().config.storage.state_dir
    root = anchored_dir(state_dir)
    folders = list(plugins_dirs) if plugins_dirs is not None else find_plugins_dirs()
    schemas = collect_schemas(folders)
    store = ComponentSettingsStore(root)
    store.reconcile("plugin", schemas)
    notes: list[str] = []
    for plugin_id, schema in schemas.items():
        current = store.load("plugin", plugin_id, schema)
        clean, plugin_notes = repair_values(schema, current)
        if clean != current:
            store.save("plugin", plugin_id, clean, schema)
            notes.extend(plugin_notes)
    print(f"Validated {len(schemas)} plugin setting schema(s).")
    if notes:
        for line in notes:
            print(line)
    else:
        print("Default settings match their schemas.")
    print(f"Settings: {root / 'plugins.json'}")
    return 0


def apply_server_plugin_defaults(
    state_dir: Path | str | None = None,
    plugins_dirs: Optional[list[Path]] = None,
) -> list[str]:
    """Write server defaults for plugins that declare them.

    A value is changed only while it is still the desktop default, so a later
    install does not wipe a setting the admin already changed.
    """
    from ..devtools.paths import anchored_dir, find_plugins_dirs
    from ..settings.loader import SettingsProvider

    if state_dir is None:
        state_dir = SettingsProvider().config.storage.state_dir
    root = anchored_dir(state_dir)
    folders = list(plugins_dirs) if plugins_dirs is not None else find_plugins_dirs()
    schemas = collect_schemas(folders)
    store = ComponentSettingsStore(root)
    notes: list[str] = []
    for plugin_id, schema in schemas.items():
        current = dict(store.load("plugin", plugin_id, schema))
        changed = False
        for field in schema.fields:
            if field.server_default is None:
                continue
            if current.get(field.key) != field.default:
                continue
            current[field.key] = field.server_default
            changed = True
            notes.append(f"{plugin_id}.{field.key} = {field.server_default!r}")
        if changed:
            saved = store.save("plugin", plugin_id, current, schema)
            if plugin_id == "plugin_web_ui":
                from ..server.settings import sync_from_plugin

                sync_from_plugin(root, saved)
    if notes:
        print("Server defaults:")
        for line in notes:
            print("  " + line)
    else:
        print("Server defaults already match, or no plugin declares them.")
    return notes


def apply_named_settings(
    state_dir: Path | str,
    plugin_id: str,
    pairs: list[tuple[str, str]],
    plugins_dirs: Optional[list[Path]] = None,
) -> tuple[int, list[str]]:
    """Save ``-s name value`` pairs. Nothing is written when a value is invalid."""
    from ..devtools.paths import find_plugins_dirs

    folders = list(plugins_dirs) if plugins_dirs is not None else find_plugins_dirs()
    schemas = collect_schemas(folders)
    schema = schemas.get(plugin_id)
    if schema is None:
        return 1, [f"Unknown plugin {plugin_id}. Run: kerniq plugins list"]
    if not pairs:
        return 1, ["Pass -s setting_name value"]
    store = ComponentSettingsStore(state_dir)
    current = store.load("plugin", plugin_id, schema)
    updated, errors = assign_settings(schema, current, pairs)
    if errors:
        return 1, errors
    saved = store.save("plugin", plugin_id, updated, schema)
    if plugin_id == "plugin_web_ui":
        from ..server.settings import sync_from_plugin

        sync_from_plugin(state_dir, saved)
    lines = [f"{plugin_id}.{key} = {saved.get(key)!r}" for key, _value in pairs]
    return 0, lines
