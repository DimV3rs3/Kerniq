"""Fields every plugin exposes to the manager, UI, and CLI."""

from __future__ import annotations

from typing import Optional

from ..interfaces.settings_schema import SettingField, SettingType, SettingsSchema


def with_manager_fields(
    schema: Optional[SettingsSchema],
    plugin_id: str,
    title: str,
) -> SettingsSchema:
    """Ensure enabled and listed exist. Do not duplicate a key the plugin already declares."""
    if schema is None:
        schema = SettingsSchema(
            component_id=plugin_id,
            component_type="plugin",
            title=title or plugin_id,
            fields=[],
        )
    keys = {field.key for field in schema.fields}
    extra = []
    if "enabled" not in keys:
        extra.append(
            SettingField(
                key="enabled",
                label="Enabled",
                type=SettingType.BOOL,
                default=True,
                description="Turn this plugin on or off. Off plugins stay in settings but are not started.",
            )
        )
    if "listed" not in keys:
        extra.append(
            SettingField(
                key="listed",
                label="Show in plugin list",
                type=SettingType.BOOL,
                default=True,
                description="When off, hide this plugin from the UI list and from kerniq plugins list. It can still run if it is enabled.",
            )
        )
    if extra:
        schema.fields = extra + list(schema.fields)
    return schema
