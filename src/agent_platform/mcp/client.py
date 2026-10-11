import asyncio
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from ..interfaces.tools import Tool, ToolResult
from .interfaces import MCPTool

class MCPClientAdapter:
    def __init__(self, server_params: StdioServerParameters):
        self.server_params = server_params
        self._session: Optional[ClientSession] = None
        self._exit_stack = None

    async def connect(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        read, write = await self._exit_stack.enter_async_context(stdio_client(self.server_params))
        self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

    async def disconnect(self):
        if self._exit_stack:
            await self._exit_stack.aclose()
        self._session = None

    async def list_tools(self) -> List[MCPTool]:
        if not self._session:
            raise RuntimeError("MCP Client not connected")
        result = await self._session.list_tools()
        return [
            MCPTool(name=t.name, description=t.description, input_schema=t.inputSchema)
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self._session:
            raise RuntimeError("MCP Client not connected")
        result = await self._session.call_tool(name, arguments)
        return result.content

    async def close(self):
        await self.disconnect()
