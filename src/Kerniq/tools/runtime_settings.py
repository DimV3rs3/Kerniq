"""Apply stored per-tool settings without hard-coding tool names."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from ..interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from ..settings.component_store import ComponentSettingsStore


def ensure_common_fields(schema: Optional[SettingsSchema], tool: Any) -> SettingsSchema:
    """Every tool exposes risk (read-only), auto-accept, and chat merge."""
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
    return schema


def apply_stored_tool_settings(tools: Iterable[Any], state_dir: Path | str) -> None:
    store = ComponentSettingsStore(state_dir)
    for tool in tools:
        schema = ensure_common_fields(tool.settings_schema() if hasattr(tool, "settings_schema") else None, tool)
        values = store.load("tool", tool.tool_id, schema)
        try:
            tool.apply_settings(values)
        except Exception:
            pass
        if "auto_accept" in values:
            tool.cfg_auto_accept = bool(values["auto_accept"])
        if "collapsible" in values:
            tool.cfg_collapsible = bool(values["collapsible"])
