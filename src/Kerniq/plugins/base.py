"""Plugin contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .manifest import PluginManifest
from ..interfaces.settings_schema import SettingsSchema


class PluginContext:
    def __init__(self, logger, config, event_bus, tool_registry):
        self.logger = logger
        self.config = config
        self.event_bus = event_bus
        self.tool_registry = tool_registry

    def register_tool(self, tool, *, expose_to_agent=None):
        """Register a tool that belongs to this plugin.

        Plugin tools are private by default. They stay in the registry so the
        plugin can call them, and they are not offered to the model, the CLI
        tool list, or MCP. Set ``_agent_visible = True`` on the tool before
        calling this, or pass ``expose_to_agent=True``, only when the model
        should see the command. A plugin folder's ``tools/`` package is loaded
        for you; the manifest flag ``[tools] expose_to_agent`` is the switch.
        """
        register = getattr(self.tool_registry, "register_tool", None)
        if register is None or tool is None:
            return
        if expose_to_agent is not None:
            tool._agent_visible = bool(expose_to_agent)
        elif "_agent_visible" not in getattr(tool, "__dict__", {}):
            tool._agent_visible = False
        tool._plugin_owned = True
        try:
            register(tool, replace=True)
        except TypeError:
            register(tool)


class Plugin(ABC):
    @property
    @abstractmethod
    def manifest(self) -> PluginManifest:
        pass

    def settings_schema(self) -> Optional[SettingsSchema]:
        """Optional settings exposed to UI/CLI."""
        return None

    def apply_settings(self, values: Dict[str, Any]) -> None:
        return None

    def extension_slots(self) -> list:
        """Slots other plugins may fill. Empty means this plugin is not a host.

        A contribution is attached only when the host lists that slot here.
        """
        return []

    def contributions(self) -> list:
        """Pieces this plugin adds to a host that allows the slot.

        Each item is a dict: host, slot, id, label, icon.
        The host decides what a slot means. This method only declares the offer.
        """
        return []

    def actions(self) -> list:
        """Buttons a shell may show. Each item is {id, label, description}.

        The shell displays them. It does not decide what running means.
        """
        return []

    async def run_action(self, action_id: str, tool_context: Any) -> Dict[str, Any]:
        raise ValueError(f"Plugin has no action {action_id}")

    @abstractmethod
    async def initialize(self, context: PluginContext) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass
