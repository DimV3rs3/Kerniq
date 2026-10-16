from typing import Dict, List, Optional, Any
from ..interfaces.tools import Tool
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools_by_id: Dict[str, Tool] = {}
        self._tools_by_name: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool, replace: bool = False):
        existing = self._tools_by_id.get(tool.tool_id)
        if existing is not None or tool.name in self._tools_by_name:
            if not replace:
                if tool.tool_id in self._tools_by_id:
                    raise ValueError(f"Tool with id {tool.tool_id} is already registered")
                raise ValueError(f"Tool with name {tool.name} is already registered")
            old = self._tools_by_id.pop(tool.tool_id, None)
            if old is not None:
                self._tools_by_name.pop(old.name, None)
            self._tools_by_name.pop(tool.name, None)
        self._tools_by_id[tool.tool_id] = tool
        self._tools_by_name[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (id: {tool.tool_id})")

    def get_tool(self, identifier: str) -> Optional[Tool]:
        # Try to find by name first, then by id
        return self._tools_by_name.get(identifier) or self._tools_by_id.get(identifier)

    def list_tools(self) -> List[Tool]:
        return list(self._tools_by_id.values())

    def get_tools_for_model(self) -> List[Dict[str, Any]]:
        # Convert tools to the format expected by LLMs (e.g., OpenAI tool spec)
        tools_spec = []
        for tool in self._tools_by_id.values():
            tools_spec.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema
                }
            })
        return tools_spec
