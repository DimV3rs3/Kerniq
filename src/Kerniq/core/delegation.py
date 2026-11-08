"""When Multi-agent is on, the main model keeps read-only tools and run_agents."""

from __future__ import annotations

from typing import Any

MUTATING = frozenset({
    "write_file",
    "edit_file",
    "create_file",
    "delete_file",
    "move_file",
    "copy_file",
    "unzip",
    "zip",
    "create_directory",
    "run_command",
    "terminal",
    "update_plan",
    "mail_send",
    "mail_forward",
    "mail_delete",
    "mail_move",
    "mail_mark",
    "mail_download",
})
_READONLY = frozenset({"low", "read_only", "readonly"})


def is_readonly_tool(name: str, risk: str) -> bool:
    if name in MUTATING or name == "run_agents":
        return False
    return str(risk or "").lower() in _READONLY


def allow_tool(name: str, risk: str, *, mode: str, enabled: bool) -> bool:
    """Plan mode never offers run_agents. Act, with the plugin on, is read-only plus that call."""
    if not enabled:
        return True
    if str(mode or "act").lower() == "plan":
        return name != "run_agents"
    if name == "run_agents":
        return True
    return is_readonly_tool(name, risk)


def multi_agent_enabled(state_dir: Any = None) -> bool:
    try:
        if state_dir is None:
            from Kerniq.settings.loader import SettingsProvider

            state_dir = SettingsProvider().config.storage.state_dir
        from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
        from Kerniq.settings.component_store import ComponentSettingsStore

        schema = SettingsSchema(
            component_id="multi_agent",
            component_type="plugin",
            title="Multi-agent",
            fields=[SettingField(key="enabled", label="Enabled", type=SettingType.BOOL, default=False)],
        )
        values = ComponentSettingsStore(state_dir).load("plugin", "multi_agent", schema)
        return bool(values.get("enabled"))
    except Exception:
        return False
