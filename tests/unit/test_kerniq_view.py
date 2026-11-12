"""`.kerniq-view` is three symlinks and must not contain itself."""

from __future__ import annotations

import asyncio
from pathlib import Path

from Kerniq.security.roots import ensure_view, prune_nested_view, resolve_virtual
from Kerniq.tools.filesystem import FileSystemTools
from Kerniq.tools.registry import ToolRegistry


def test_view_links_the_real_folders_and_drops_a_nested_copy(tmp_path):
    workspace = tmp_path / "Kerniq"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
    nested = workspace / ".kerniq-view"
    nested.mkdir()
    (nested / "workspace").symlink_to(workspace, target_is_directory=True)
    (nested / "attachments").symlink_to(workspace, target_is_directory=True)
    view = ensure_view(workspace)
    assert not nested.exists()
    assert view != workspace
    assert not str(view.resolve()).startswith(str(workspace.resolve()) + "/")
    assert (view / "workspace").is_symlink()
    assert (view / "workspace").resolve() == workspace.resolve()
    assert (view / "attachments").resolve() == (workspace / "attachments").resolve()
    assert (view / "downloads").resolve() == (workspace / ".downloads").resolve()
    assert sorted(path.name for path in view.iterdir()) == ["attachments", "downloads", "workspace"]
    assert not (workspace / ".kerniq-view").exists()
    # Following the workspace link does not walk back into the view.
    assert not any(path.name == ".kerniq-view" for path in (view / "workspace").iterdir())


def test_list_root_is_the_three_links_and_paths_share_one_resolver(tmp_path):
    (tmp_path / "a.txt").write_text("hi", encoding="utf-8")
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("no", encoding="utf-8")

    async def run():
        registry = ToolRegistry()
        for tool in FileSystemTools(str(tmp_path)).get_tools():
            registry.register_tool(tool)
        listed = await registry.get_tool("list_directory").execute({"path": ".", "tool_call_id": "1"}, None)
        assert [item["name"] for item in listed.output["entries"]] == ["workspace", "attachments", "downloads"]
        read = registry.get_tool("read_file")
        for path in ("a.txt", "./a.txt", "workspace/a.txt", "./workspace/a.txt"):
            result = await read.execute({"path": path, "tool_call_id": path}, None)
            assert result.status == "success", path
            assert "hi" in result.human_readable
        denied = await read.execute({"path": "workspace/../secret.txt", "tool_call_id": "x"}, None)
        assert denied.status == "error"
        return True

    assert asyncio.run(run())
    assert resolve_virtual("downloads/note.bin", tmp_path) == (tmp_path / ".downloads" / "note.bin")
    prune_nested_view(tmp_path)


def test_install_root_keeps_attachments_when_the_workspace_moves(tmp_path, monkeypatch):
    install = tmp_path / "Kerniq"
    install.mkdir()
    custom = tmp_path / "elsewhere" / "downs"
    workspace = tmp_path / "snap"
    workspace.mkdir()
    monkeypatch.setenv("KERNIQ_ROOT", str(install))
    monkeypatch.setattr(
        "Kerniq.security.roots._peek_folder_settings",
        lambda: ("./attachments", str(custom)),
    )
    from Kerniq.security.roots import desktop_roots

    roots = desktop_roots(workspace)
    assert roots.workspace == workspace.resolve()
    assert roots.attachments == (install / "attachments").resolve()
    assert roots.downloads == custom.resolve()
    view = ensure_view(workspace)
    assert (view / "attachments").resolve() == roots.attachments
    assert (view / "downloads").resolve() == custom.resolve()
    assert not (workspace / "attachments").exists()
    assert not (workspace / ".downloads").exists()


def test_outside_attachments_can_be_read_and_deleted_but_not_edited(tmp_path, monkeypatch):
    install = tmp_path / "Kerniq"
    install.mkdir()
    workspace = tmp_path / "snap"
    workspace.mkdir()
    monkeypatch.setenv("KERNIQ_ROOT", str(install))
    monkeypatch.setattr(
        "Kerniq.security.roots._peek_folder_settings",
        lambda: ("./attachments", "./downloads"),
    )
    note = install / "attachments" / "note.txt"
    note.parent.mkdir(parents=True)
    note.write_text("keep", encoding="utf-8")
    tools = {t.name: t for t in FileSystemTools(str(workspace)).get_tools()}

    async def run():
        read = await tools["read_file"].execute({"path": "./attachments/note.txt"}, None)
        assert read.status == "success"
        assert "keep" in (read.human_readable or "")
        edited = await tools["write_file"].execute(
            {"path": "./attachments/note.txt", "content": "no"}, None
        )
        assert edited.status == "error"
        assert note.read_text(encoding="utf-8") == "keep"
        copied = await tools["copy_file"].execute(
            {"src": "./attachments/note.txt", "dst": "note.txt"}, None
        )
        assert copied.status == "success", copied.human_readable
        assert (workspace / "note.txt").read_text(encoding="utf-8") == "keep"
        deleted = await tools["delete_file"].execute({"path": "attachments/note.txt"}, None)
        assert deleted.status == "success", deleted.human_readable
        assert not note.exists()
        escaped = await tools["write_file"].execute(
            {"path": "workspace/../../escape_attempt.txt", "content": "ESCAPE"}, None
        )
        assert escaped.status == "error"
        assert not (workspace.parent / "escape_attempt.txt").exists()
        assert not (install.parent / "escape_attempt.txt").exists()

    asyncio.run(run())


def test_unzip_from_downloads_lands_in_the_workspace(tmp_path, monkeypatch):
    import zipfile

    install = tmp_path / "Kerniq"
    install.mkdir()
    workspace = tmp_path / "snap"
    workspace.mkdir()
    monkeypatch.setenv("KERNIQ_ROOT", str(install))
    monkeypatch.setattr(
        "Kerniq.security.roots._peek_folder_settings",
        lambda: ("./attachments", "./downloads"),
    )
    archive = install / "downloads" / "bundle.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("inside.txt", "from-zip")
    tools = {t.name: t for t in FileSystemTools(str(workspace)).get_tools()}

    async def run():
        result = await tools["unzip"].execute({"archive": "./downloads/bundle.zip"}, None)
        assert result.status == "success", result.human_readable
        assert (workspace / "bundle" / "inside.txt").read_text(encoding="utf-8") == "from-zip"
        assert not (archive.parent / "bundle").exists()

    asyncio.run(run())


def test_unzip_reads_tar_gz_and_skips_a_parent_path(tmp_path):
    import io
    import tarfile

    workspace = tmp_path / "ws"
    workspace.mkdir()
    archive = workspace / "src.tar.gz"
    outside = tmp_path / "escaped.txt"
    with tarfile.open(archive, "w:gz") as handle:
        info = tarfile.TarInfo("inside.txt")
        payload = b"from-tar"
        info.size = len(payload)
        handle.addfile(info, io.BytesIO(payload))
        evil = tarfile.TarInfo("../escaped.txt")
        body = b"nope"
        evil.size = len(body)
        handle.addfile(evil, io.BytesIO(body))
    tools = {tool.name: tool for tool in FileSystemTools(str(workspace)).get_tools()}

    async def run():
        result = await tools["unzip"].execute({"archive": "src.tar.gz"}, None)
        assert result.status == "success", result.human_readable
        assert (workspace / "src" / "inside.txt").read_bytes() == b"from-tar"
        assert not outside.exists()
        packed = await tools["zip"].execute({"path": "src/inside.txt", "archive": "out.tar.gz"}, None)
        assert packed.status == "success", packed.human_readable
        assert (workspace / "out.tar.gz").is_file()

    asyncio.run(run())
