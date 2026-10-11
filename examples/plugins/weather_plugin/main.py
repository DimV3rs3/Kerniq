"""Example weather plugin."""

from __future__ import annotations

from typing import Any, Dict

from agent_platform.plugins.base import Plugin, PluginContext
from agent_platform.plugins.manifest import PluginManifest
from agent_platform.interfaces.tools import Tool, ToolResult


class WeatherTool(Tool):
    @property
    def tool_id(self) -> str:
        return "weather_get"

    @property
    def name(self) -> str:
        return "get_weather"

    @property
    def description(self) -> str:
        return "Gets the current weather for a city (mock data)."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        city = arguments.get("city", "Unknown")
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", "unknown"),
            tool_id=self.tool_id,
            status="success",
            output={"temp": 20, "condition": "Sunny"},
            human_readable=f"The weather in {city} is Sunny and 20 degrees.",
        )


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="plugin_weather",
            name="Weather Plugin",
            version="1.0.0",
            api_version="1.0",
            entry_point="main.PluginImpl",
            description="Provides weather information tools",
            capabilities=["tools"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    async def initialize(self, context: PluginContext) -> bool:
        context.register_tool(WeatherTool())
        if context.logger:
            context.logger.info("Weather plugin initialized")
        return True

    async def shutdown(self) -> None:
        pass
