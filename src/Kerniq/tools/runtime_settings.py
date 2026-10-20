"""Apply stored per-tool settings without hard-coding tool names."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from ..interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from ..settings.component_store import ComponentSettingsStore


def _plan_default(tool: Any) -> bool:
    method = getattr(tool, "plan_membership_default", None)
    if callable(method):
        try:
            return bool(method())
        except Exception:
            return False
    return bool(getattr(tool, "include_in_plan", False))


def ensure_common_fields(schema: Optional[SettingsSchema], tool: Any) -> SettingsSchema:
    """Every tool exposes risk (read-only), auto-accept, chat merge, and Plan membership."""
    if schema is None:
        schema = SettingsSchema(
            component_id=getattr(tool, "tool_id", "tool"),
            component_type="tool",
            title=getattr(tool, "name", "tool"),
            fields=[],
        )
    keys = {f.key for f in schema.fields}
    if "auto_accept" not in keys:
        schema.fields.append(
            SettingField(
                key="auto_accept",
                label="Auto-accept this tool",
                type=SettingType.BOOL,
                default=False,
                description=(
                    "Skip the confirmation prompt for this tool regardless of its risk. "
                    "Critical risk is never auto-accepted."
                ),
            )
        )
    if "collapsible" not in keys:
        schema.fields.append(
            SettingField(
                key="collapsible",
                label="Merge consecutive calls in chat",
                type=SettingType.BOOL,
                default=True,
                description="When chat aggregation is on, consecutive calls of this tool merge into one block",
            )
        )
    if "include_in_plan" not in keys:
        schema.fields.append(
            SettingField(
                key="include_in_plan",
                label="Include in Plan mode",
                type=SettingType.BOOL,
                default=_plan_default(tool),
                description=(
                    "Plan mode may call this tool. Writes, commands, and other changes "
                    "stay off until this is on."
                ),
            )
        )
    return schema


def apply_stored_tool_settings(tools: Iterable[Any], state_dir: Path | str) -> None:
    store = ComponentSettingsStore(state_dir)
    schemas = {}
    for tool in tools:
        schema = ensure_common_fields(tool.settings_schema() if hasattr(tool, "settings_schema") else None, tool)
        schemas[tool.tool_id] = schema
        values = store.load("tool", tool.tool_id, schema)
        try:
            tool.apply_settings(values)
        except Exception:
            pass
        if "auto_accept" in values:
            tool.cfg_auto_accept = bool(values["auto_accept"])
        if "collapsible" in values:
            tool.cfg_collapsible = bool(values["collapsible"])
        if "include_in_plan" in values:
            tool.cfg_include_in_plan = bool(values["include_in_plan"])
    store.reconcile("tool", schemas)
    _drop_stale_enabled(state_dir, schemas, tools)


def _drop_stale_enabled(state_dir: Path | str, schemas: dict[str, Any], tools: Iterable[Any]) -> None:
    """A tool that is no longer installed does not keep an enabled flag."""
    from ..settings.file import TOOLS_FILE, read_state_file, write_state_file

    raw = read_state_file(state_dir, TOOLS_FILE)
    if not isinstance(raw.get("enabled_tools"), dict):
        return
    live_ids = set(schemas)
    live_names = {getattr(tool, "name", "") for tool in tools}
    enabled = raw["enabled_tools"]
    cleaned = {key: value for key, value in enabled.items() if key in live_ids or key in live_names}
    if cleaned != enabled:
        raw["enabled_tools"] = cleaned
        write_state_file(state_dir, TOOLS_FILE, raw)
