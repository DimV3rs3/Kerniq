"""Filesystem tool expansion tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

from Kerniq.tools.filesystem import FileSystemTools
from Kerniq.tools.registry import ToolRegistry


def test_create_edit_delete_list_recursive(tmp_path):
    async def _run():
        fs = FileSystemTools(str(tmp_path))
        reg = ToolRegistry()
        for t in fs.get_tools():
            reg.register_tool(t)

        create = reg.get_tool("create_file")
        r = await create.execute({"path": "a.txt", "content": "hello", "tool_call_id": "1"}, None)
        assert r.status == "success"

        r2 = await create.execute({"path": "a.txt", "content": "x", "tool_call_id": "2"}, None)
        assert r2.status == "error"

        edit = reg.get_tool("edit_file")
        r3 = await edit.execute(
            {"path": "a.txt", "old_string": "hello", "new_string": "hi", "tool_call_id": "3"},
            None,
        )
        assert r3.status == "success"
        assert (tmp_path / "a.txt").read_text() == "hi"

        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b")
        lst = reg.get_tool("list_directory")
        r4 = await lst.execute({"path": ".", "recursive": True, "tool_call_id": "4"}, None)
        assert r4.status == "success"
        paths = [e["path"] for e in r4.output["entries"]]
        assert any("sub" in p for p in paths)

        delete = reg.get_tool("delete_file")
        r5 = await delete.execute({"path": "a.txt", "tool_call_id": "5"}, None)
        assert r5.status == "success"
        assert not (tmp_path / "a.txt").exists()

    asyncio.run(_run())


def test_tool_settings_persist(tmp_path):
    from Kerniq.tools.settings import ToolSettingsStore

    store = ToolSettingsStore(tmp_path)
    store.update(web_search_enabled=False, fs_list_max_depth=3)
    store2 = ToolSettingsStore(tmp_path)
    assert store2.settings.web_search_enabled is False
    assert store2.settings.fs_list_max_depth == 3
    assert (tmp_path / "tools.json").is_file()
    assert not (tmp_path / "tool_settings.json").exists()
    assert not (tmp_path / "settings.json").exists()
