"""MCP server adapter: expose selected internal tools over MCP (stdio).

Compatible with official `mcp` package >= 2.0 (low-level Server + stdio transport).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from Kerniq.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class _MCPExecContext:
    """Minimal execution context for tools invoked via MCP."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = str(workspace)
        self.workspace_path = workspace


class MCPServerAdapter:
    """Publish allow-listed ToolRegistry tools as an MCP server over stdio."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        allowed_tools: Optional[Sequence[str]] = None,
        workspace: Optional[Path] = None,
        server_name: str = "kerniq-mcp",
        version: str = "0.1.3",
        security_policy: Any = None,
    ) -> None:
        self.tool_registry = tool_registry
        # Safe default: empty allowlist publishes nothing
        self.allowed_tools: List[str] = list(allowed_tools or [])
        self.workspace = Path(workspace or ".").resolve()
        self.server_name = server_name
        self.version = version
        self.security_policy = security_policy

    def _is_allowed(self, tool_id: str, name: str) -> bool:
        if not self.allowed_tools:
            return False
        return tool_id in self.allowed_tools or name in self.allowed_tools

    def published_tools(self) -> List[Any]:
        out = []
        for t in self.tool_registry.list_tools():
            if self._is_allowed(t.tool_id, t.name):
                out.append(t)
        return out

    def _build_server(self) -> Any:
        try:
            from mcp.server.lowlevel.server import Server
            from mcp import types
        except ImportError as e:
            raise RuntimeError(
                "MCP SDK not installed. Install with: pip install 'Kerniq[mcp]'  (or: pip install mcp)"
            ) from e

        registry = self.tool_registry
        workspace = self.workspace
        allowed = self.allowed_tools

        def is_allowed(tool_id: str, name: str) -> bool:
            if not allowed:
                return False
            return tool_id in allowed or name in allowed

        async def on_list_tools(ctx: Any, params: Any) -> Any:
            tools = []
            for t in registry.list_tools():
                if not is_allowed(t.tool_id, t.name):
                    continue
                schema = t.input_schema or {"type": "object", "properties": {}}
                tools.append(
                    types.Tool(
                        name=t.name,
                        description=t.description or t.name,
                        input_schema=schema,
                    )
                )
            return types.ListToolsResult(tools=tools)

        async def on_call_tool(ctx: Any, params: Any) -> Any:
            name = getattr(params, "name", None) or ""
            arguments = getattr(params, "arguments", None) or {}
            if not isinstance(arguments, dict):
                arguments = {}

            internal = registry.get_tool(name)
            if internal is None or not is_allowed(internal.tool_id, internal.name):
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"Tool not found or not published: {name}")],
                    is_error=True,
                )

            exec_ctx = _MCPExecContext(workspace)
            args = dict(arguments)
            args.setdefault("tool_call_id", f"mcp-{name}")
            policy = self.security_policy
            if policy is not None:
                from Kerniq.security.policy import PolicyDecision

                decision = policy.evaluate_tool_call(
                    internal.name, args, getattr(internal, "risk_level", "medium"), tool=internal
                )
                if decision != PolicyDecision.ALLOW:
                    why = "denied by security policy"
                    if decision == PolicyDecision.REQUIRE_APPROVAL:
                        why = "requires human approval and is not allowed over MCP"
                    if internal.name in ("run_command", "terminal"):
                        reason = policy.terminal_block_reason(str(args.get("command", "")))
                        if reason:
                            why = reason
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=f"ERROR: {why}")],
                        is_error=True,
                    )
            try:
                result = await internal.execute(args, exec_ctx)
                if result.success:
                    text = result.human_readable
                    if not text and result.output is not None:
                        import json

                        text = json.dumps(result.output, ensure_ascii=False, default=str)
                    if not text:
                        text = "OK"
                    return types.CallToolResult(
                        content=[types.TextContent(type="text", text=text)],
                        is_error=False,
                    )
                err = result.error or result.human_readable or "tool failed"
                return types.CallToolResult(
                    content=[types.TextContent(type="text", text=f"ERROR: {err}")],
                    is_error=True,
                )
            except Exception as e:
                logger.exception("MCP tool %s failed", name)
                return types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text", text=f"ERROR: {type(e).__name__}: {e}"
                        )
                    ],
                    is_error=True,
                )

        server = Server(
            self.server_name,
            version=self.version,
            description="Kerniq AI Agent Platform MCP server",
            on_list_tools=on_list_tools,
            on_call_tool=on_call_tool,
        )
        return server

    async def run_stdio(self) -> None:
        """Run MCP server on process stdin/stdout until the client disconnects."""
        try:
            from mcp.server.stdio import stdio_server
            from mcp.server.lowlevel.server import NotificationOptions
        except ImportError:
            from mcp.server.stdio import stdio_server

            NotificationOptions = None  # type: ignore

        server = self._build_server()
        names = [t.name for t in self.published_tools()]
        logger.info(
            "MCP server %s starting (stdio), published=%s, workspace=%s",
            self.server_name,
            names or "(none — set [mcp] published_tools in config)",
            self.workspace,
        )
        # stderr so clients reading stdout only see protocol frames
        print(
            f"kerniq-mcp: ready tools={names or []} workspace={self.workspace}",
            flush=True,
            file=__import__("sys").stderr,
        )

        init_opts = server.create_initialization_options()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, init_opts)

    async def run(self) -> None:
        await self.run_stdio()


async def run_mcp_server(
    tool_registry: ToolRegistry,
    allowed_tools: Optional[Sequence[str]] = None,
    workspace: Optional[Path] = None,
    security_policy: Any = None,
) -> None:
    adapter = MCPServerAdapter(
        tool_registry=tool_registry,
        allowed_tools=allowed_tools,
        workspace=workspace,
        security_policy=security_policy,
    )
    await adapter.run_stdio()
