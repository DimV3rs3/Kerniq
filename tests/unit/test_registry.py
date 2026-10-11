"""Unit tests for tool registry."""

from __future__ import annotations

from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.filesystem import FileSystemTools


def test_register_and_list(tmp_path):
    registry = ToolRegistry()
    fs = FileSystemTools(workspace=str(tmp_path))
    for t in fs.get_tools():
        registry.register_tool(t)
    tools = registry.list_tools()
    assert len(tools) >= 8
    assert registry.get_tool("read_file") is not None
    assert registry.get_tool("edit_file") is not None
    assert registry.get_tool("delete_file") is not None
    assert registry.get_tool("create_file") is not None
    specs = registry.get_tools_for_model()
    assert all("function" in s for s in specs)


def test_duplicate_registration_raises(tmp_path):
    registry = ToolRegistry()
    fs = FileSystemTools(workspace=str(tmp_path))
    tools = fs.get_tools()
    registry.register_tool(tools[0])
    try:
        registry.register_tool(tools[0])
        assert False, "Expected ValueError"
    except ValueError:
        pass
