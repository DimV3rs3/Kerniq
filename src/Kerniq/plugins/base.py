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

    def register_tool(self, tool):
        self.tool_registry.register_tool(tool)


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

    @abstractmethod
    async def initialize(self, context: PluginContext) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass
