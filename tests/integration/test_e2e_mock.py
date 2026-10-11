"""End-to-end offline test with MockProvider."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent_platform.core.agent import Agent
from agent_platform.models.providers.mock import MockProvider
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.filesystem import FileSystemTools
from agent_platform.interfaces.models import ModelResponse, Message, MessageRole, ToolCall


def test_end_to_end_mock_flow(tmp_path):
    async def _run():
        workspace = tmp_path / "agent_workspace"
        workspace.mkdir()
        (workspace / "hello.txt").write_text("Hello World")

        registry = ToolRegistry()
        for tool in FileSystemTools(workspace=str(workspace)).get_tools():
            registry.register_tool(tool)

        responses = [
            ModelResponse(
                messages=[
                    Message(
                        role=MessageRole.ASSISTANT,
                        content="I will read the file.",
                        tool_calls=[
                            ToolCall(
                                id="call_1",
                                name="read_file",
                                arguments={"path": "hello.txt"},
                            )
                        ],
                    )
                ],
                finish_reason="tool_calls",
            ),
            ModelResponse(
                messages=[
                    Message(
                        role=MessageRole.ASSISTANT,
                        content="The file contains: Hello World",
                    )
                ],
                finish_reason="stop",
            ),
        ]
        provider = MockProvider(responses=responses)
        agent = Agent(provider, registry)
        result = await agent.run("What is in hello.txt?", workspace=str(workspace))
        assert "Hello World" in result

    asyncio.run(_run())


def test_mock_provider_default_response():
    async def _run():
        from agent_platform.interfaces.models import ModelRequest
        from uuid import uuid4

        provider = MockProvider()
        req = ModelRequest(messages=[], session_id=uuid4())
        resp = await provider.generate(req)
        assert resp.messages
        assert resp.finish_reason == "stop"
        assert await provider.check_connection() is True

    asyncio.run(_run())


def test_filesystem_workspace_escape(tmp_path):
    async def _run():
        workspace = tmp_path / "ws"
        workspace.mkdir()
        registry = ToolRegistry()
        for t in FileSystemTools(workspace=str(workspace)).get_tools():
            registry.register_tool(t)
        read_tool = registry.get_tool("read_file")
        result = await read_tool.execute(
            {"path": "../secret.txt", "tool_call_id": "c1"}, None
        )
        assert result.status == "error"
        assert "outside" in result.human_readable.lower() or "denied" in result.human_readable.lower()

    asyncio.run(_run())
