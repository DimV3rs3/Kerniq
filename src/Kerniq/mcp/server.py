import asyncio
from typing import List, Dict, Any, Optional
from mcp.server import Server, NotificationOptions
from mcp.server.models import Tool, TextContent
from mcp.server.stdio import stdio_server
from ..interfaces.tools import Tool as InternalTool
from ..tools.registry import ToolRegistry

class MCPServerAdapter:
    def __init__(self, tool_registry: ToolRegistry, allowed_tools: List[str] = None):
        self.tool_registry = tool_registry
        self.allowed_tools = allowed_tools # If None, all are allowed (not recommended)
        self.server = Server("agent-platform-mcp")

    def _get_published_tools(self) -> List[Tool]:
        all_tools = self.tool_registry.list_tools()
        published = []
        for t in all_tools:
            if self.allowed_tools is None or t.tool_id in self.allowed_tools:
                published.append(
                    Tool(
                        name=t.name,
                        description=t.description,
                        inputSchema=t.input_schema
                    )
                )
        return published

    async def setup(self):
        # Register tool handlers
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            return self._get_published_tools()

        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            # Find the internal tool by name or id
            internal_tool = self.tool_registry.get_tool(name)
            if not internal_tool:
                raise ValueError(f"Tool {name} not found")

            # We need a context for execution. In MCP server mode, 
            # we might use a default or session-based context.
            # For now, we create a dummy context with basic workspace info.
            class DummyContext:
                def __init__(self): self.workspace = "."
            
            result = await internal_tool.execute(arguments, DummyContext())
            
            return [
                TextContent(type="text", text=result.human_readable)
            ]

    async def run(self):
        await self.setup()
        async with stdio_server() as (read, write):
            await self.server.run(
                read,
                write,
                # Notification options can be added here
            )
