import os
from pathlib import Path
from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.interfaces.tools import Tool, ToolResult
from typing import Dict, Any

class WeatherTool(Tool):
    @property
    def tool_id(self) -> str: return "weather_get"
    @property
    def name(self) -> str: return "get_weather"
    @property
    def description(self) -> str: return "Gets the current weather for a city."
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        city = arguments.get("city", "Unknown")
        # Mock weather data
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", "unknown"),
            tool_id=self.tool_id,
            status="success",
            output={"temp": 20, "condition": "Sunny"},
            human_readable=f"The weather in {city} is Sunny and 20 degrees."
        )

class WeatherPlugin(Plugin):
    def __init__(self):
        self.name = "Weather Plugin"
        self.version = "1.0.0"
        self.plugin_id = "plugin_weather"

    async def initialize(self, context: PluginContext):
        # Register the weather tool
        context.register_tool(WeatherTool())
        return True

    async def shutdown(self):
        pass
