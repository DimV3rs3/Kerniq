"""Filesystem tools with workspace boundary enforcement."""

from __future__ import annotations

from typing import Dict, Any, List
import pathlib
import os
import shutil

from ..interfaces.tools import Tool, ToolResult
from ..interfaces.settings_schema import SettingsSchema, SettingField, SettingType


class FileSystemToolBase(Tool):
    def __init__(self, workspace: pathlib.Path):
        self.workspace = pathlib.Path(workspace).resolve()
        self._cfg_keys: tuple = ()

    @property
    def category(self) -> str:
        return "filesystem"

    def settings_schema(self) -> SettingsSchema | None:
        return None

    def apply_settings(self, values: dict) -> None:
        for k, v in (values or {}).items():
            attr = f"cfg_{k}"
            if hasattr(self, attr) or k in getattr(self, "_cfg_keys", ()):
                setattr(self, attr, v)

    def _safe_path(self, path_str: str, *, must_exist: bool = False) -> pathlib.Path:
        base = self.workspace
        target = (base / path_str).resolve()
        if not target.is_relative_to(base):
            raise PermissionError(f"Access denied: {path_str} is outside workspace")
        if must_exist and not target.exists():
            raise FileNotFoundError(f"Path does not exist: {path_str}")
        return target

    def _create_error_result(self, call_id: str, msg: str, error_code: str) -> ToolResult:
        return ToolResult(
            tool_call_id=call_id,
            tool_id=self.tool_id,
            status="error",
            output=None,
            human_readable=msg,
            error=error_code,
        )


class FileExistsTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_file_exists"

    @property
    def name(self) -> str:
        return "file_exists"

    @property
    def description(self) -> str:
        return "Checks if a file or directory exists at the given path relative to the workspace."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"])
            exists = path.exists()
            kind = "directory" if path.is_dir() else ("file" if path.is_file() else "other")
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"exists": exists, "kind": kind if exists else None},
                human_readable=f"Exists: {exists}" + (f" ({kind})" if exists else ""),
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class ReadFileTool(FileSystemToolBase):
    def __init__(self, workspace: pathlib.Path):
        super().__init__(workspace)
        self.cfg_max_bytes = 200000

    def settings_schema(self) -> SettingsSchema | None:
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="max_bytes",
                    label="Default max read bytes",
                    type=SettingType.INT,
                    default=200000,
                    minimum=1024,
                    maximum=20_000_000,
                ),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if values and "max_bytes" in values:
            self.cfg_max_bytes = int(values["max_bytes"])

    @property
    def tool_id(self) -> str:
        return "fs_read_file"

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads the content of a text file relative to the workspace."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "max_bytes": {"type": "integer", "default": 200000},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"], must_exist=True)
            if not path.is_file():
                return self._create_error_result(call_id, f"Not a file: {arguments['path']}", "FS_ERROR")
            max_bytes = int(arguments.get("max_bytes", self.cfg_max_bytes))
            data = path.read_bytes()
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            content = data.decode("utf-8", errors="replace")
            note = "\n...[truncated]" if truncated else ""
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"content": content, "truncated": truncated, "size": path.stat().st_size},
                human_readable=f"Content of {arguments['path']}:\n{content}{note}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class WriteFileTool(FileSystemToolBase):
    def __init__(self, workspace: pathlib.Path):
        super().__init__(workspace)
        self.cfg_max_content_chars = 500000

    def settings_schema(self) -> SettingsSchema | None:
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="max_content_chars",
                    label="Max content length (chars)",
                    type=SettingType.INT,
                    default=500000,
                    minimum=1000,
                    maximum=20_000_000,
                    description="Reject write if content exceeds this size",
                ),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if values and "max_content_chars" in values:
            self.cfg_max_content_chars = int(values["max_content_chars"])

    @property
    def tool_id(self) -> str:
        return "fs_write_file"

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Creates or overwrites a file with the given content (relative to workspace)."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "create_dirs": {"type": "boolean", "default": True},
            },
            "required": ["path", "content"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"])
            if arguments.get("create_dirs", True):
                path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments["content"], encoding="utf-8")
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": str(path.relative_to(self.workspace)), "bytes": path.stat().st_size},
                human_readable=f"Successfully wrote to {arguments['path']}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class CreateFileTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_create_file"

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return "Creates a new file; fails if the file already exists."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "default": ""},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"])
            if path.exists():
                return self._create_error_result(
                    call_id, f"File already exists: {arguments['path']}", "FS_EXISTS"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(arguments.get("content", ""), encoding="utf-8")
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": arguments["path"]},
                human_readable=f"Created file {arguments['path']}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class EditFileTool(FileSystemToolBase):
    def __init__(self, workspace: pathlib.Path):
        super().__init__(workspace)
        self.cfg_min_old_chars = 1
        self.cfg_max_old_chars = 100000
        self.cfg_min_new_chars = 0
        self.cfg_max_new_chars = 200000

    def settings_schema(self) -> SettingsSchema | None:
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="min_old_chars", label="Min old_string length", type=SettingType.INT, default=1, minimum=0, maximum=1000000),
                SettingField(key="max_old_chars", label="Max old_string length", type=SettingType.INT, default=100000, minimum=1, maximum=5000000),
                SettingField(key="min_new_chars", label="Min new_string length", type=SettingType.INT, default=0, minimum=0, maximum=1000000),
                SettingField(key="max_new_chars", label="Max new_string length", type=SettingType.INT, default=200000, minimum=1, maximum=5000000),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if not values:
            return
        self.cfg_min_old_chars = int(values.get("min_old_chars", self.cfg_min_old_chars))
        self.cfg_max_old_chars = int(values.get("max_old_chars", self.cfg_max_old_chars))
        self.cfg_min_new_chars = int(values.get("min_new_chars", self.cfg_min_new_chars))
        self.cfg_max_new_chars = int(values.get("max_new_chars", self.cfg_max_new_chars))

    @property
    def tool_id(self) -> str:
        return "fs_edit_file"

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edits an existing file. Provide either (old_string + new_string) for "
            "search-replace, or 'content' for full overwrite."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_string": {"type": "string"},
                "new_string": {"type": "string"},
                "content": {"type": "string"},
                "replace_all": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"], must_exist=True)
            if not path.is_file():
                return self._create_error_result(call_id, f"Not a file: {arguments['path']}", "FS_ERROR")

            if "content" in arguments and arguments["content"] is not None and "old_string" not in arguments:
                path.write_text(arguments["content"], encoding="utf-8")
                return ToolResult(
                    tool_call_id=call_id,
                    tool_id=self.tool_id,
                    status="success",
                    output={"mode": "overwrite"},
                    human_readable=f"Overwrote {arguments['path']}",
                )

            old = arguments.get("old_string")
            new = arguments.get("new_string")
            if old is not None and new is not None:
                if not (self.cfg_min_old_chars <= len(old) <= self.cfg_max_old_chars):
                    return self._create_error_result(
                        call_id,
                        f"old_string length {len(old)} outside [{self.cfg_min_old_chars}, {self.cfg_max_old_chars}]",
                        "FS_LIMIT",
                    )
                if not (self.cfg_min_new_chars <= len(new) <= self.cfg_max_new_chars):
                    return self._create_error_result(
                        call_id,
                        f"new_string length {len(new)} outside [{self.cfg_min_new_chars}, {self.cfg_max_new_chars}]",
                        "FS_LIMIT",
                    )
            if old is None or new is None:
                return self._create_error_result(
                    call_id,
                    "Provide either content (overwrite) or old_string+new_string (replace)",
                    "FS_ARG",
                )

            text = path.read_text(encoding="utf-8")
            if old not in text:
                return self._create_error_result(
                    call_id, f"old_string not found in {arguments['path']}", "FS_NOT_FOUND"
                )
            if arguments.get("replace_all"):
                updated = text.replace(old, new)
                count = text.count(old)
            else:
                if text.count(old) > 1:
                    return self._create_error_result(
                        call_id,
                        "old_string appears multiple times; set replace_all=true or make it unique",
                        "FS_AMBIGUOUS",
                    )
                updated = text.replace(old, new, 1)
                count = 1
            path.write_text(updated, encoding="utf-8")
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"mode": "replace", "replacements": count},
                human_readable=f"Edited {arguments['path']} ({count} replacement(s))",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class DeleteFileTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_delete_file"

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Deletes a file or empty directory relative to the workspace. Use recursive=true for non-empty dirs."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean", "default": False},
            },
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"], must_exist=True)
            if path == self.workspace:
                return self._create_error_result(call_id, "Cannot delete workspace root", "FS_DENIED")
            if path.is_dir():
                if arguments.get("recursive"):
                    shutil.rmtree(path)
                else:
                    path.rmdir()
            else:
                path.unlink()
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"deleted": arguments["path"]},
                human_readable=f"Deleted {arguments['path']}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class CreateDirectoryTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_create_directory"

    @property
    def name(self) -> str:
        return "create_directory"

    @property
    def description(self) -> str:
        return "Creates a directory (and parents) relative to the workspace."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"])
            path.mkdir(parents=True, exist_ok=True)
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": arguments["path"]},
                human_readable=f"Directory ready: {arguments['path']}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class ListDirectoryTool(FileSystemToolBase):
    def __init__(self, workspace: pathlib.Path):
        super().__init__(workspace)
        self.cfg_default_max_depth = 5
        self.cfg_default_max_entries = 500
        self._cfg_keys = ("default_max_depth", "default_max_entries")

    def settings_schema(self) -> SettingsSchema | None:
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="default_max_depth",
                    label="Default max depth (recursive)",
                    type=SettingType.INT,
                    default=5,
                    minimum=0,
                    maximum=50,
                    description="Used when the model omits max_depth",
                ),
                SettingField(
                    key="default_max_entries",
                    label="Default max entries",
                    type=SettingType.INT,
                    default=500,
                    minimum=1,
                    maximum=10000,
                ),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if not values:
            return
        if "default_max_depth" in values:
            self.cfg_default_max_depth = int(values["default_max_depth"])
        if "default_max_entries" in values:
            self.cfg_default_max_entries = int(values["default_max_entries"])

    @property
    def tool_id(self) -> str:
        return "fs_list_dir"

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return (
            "Lists files in a directory relative to the workspace. "
            "Set recursive=true to walk the tree (with optional max_depth)."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "default": "."},
                "recursive": {"type": "boolean", "default": False},
                "max_depth": {"type": "integer", "default": 5},
                "max_entries": {"type": "integer", "default": 500},
            },
            "required": [],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path_str = arguments.get("path", ".")
            path = self._safe_path(path_str)
            if not path.is_dir():
                return self._create_error_result(call_id, f"Not a directory: {path_str}", "FS_ERROR")

            recursive = bool(arguments.get("recursive", False))
            max_depth = int(arguments.get("max_depth", self.cfg_default_max_depth))
            max_entries = int(arguments.get("max_entries", self.cfg_default_max_entries))
            entries: List[Dict[str, Any]] = []

            if not recursive:
                for f in sorted(path.iterdir(), key=lambda p: p.name):
                    rel = str(f.relative_to(self.workspace))
                    entries.append(
                        {
                            "name": f.name,
                            "path": rel,
                            "type": "dir" if f.is_dir() else "file",
                            "size": f.stat().st_size if f.is_file() else None,
                        }
                    )
                    if len(entries) >= max_entries:
                        break
            else:
                base_depth = len(path.parts)
                for root, dirs, files in os.walk(path):
                    root_path = pathlib.Path(root)
                    depth = len(root_path.parts) - base_depth
                    if depth > max_depth:
                        dirs.clear()
                        continue
                    for name in sorted(dirs) + sorted(files):
                        item = root_path / name
                        try:
                            item.resolve().relative_to(self.workspace)
                        except ValueError:
                            continue
                        rel = str(item.relative_to(self.workspace))
                        entries.append(
                            {
                                "name": name,
                                "path": rel,
                                "type": "dir" if item.is_dir() else "file",
                                "depth": depth,
                                "size": item.stat().st_size if item.is_file() else None,
                            }
                        )
                        if len(entries) >= max_entries:
                            break
                    if len(entries) >= max_entries:
                        break

            truncated = len(entries) >= max_entries
            lines = [f"{'d' if e['type']=='dir' else 'f'} {e['path']}" for e in entries]
            hr = f"Listing {path_str} ({len(entries)} entries"
            if truncated:
                hr += ", truncated"
            hr += "):\n" + "\n".join(lines)
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"entries": entries, "truncated": truncated},
                human_readable=hr,
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class GetFileInfoTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_get_file_info"

    @property
    def name(self) -> str:
        return "get_file_info"

    @property
    def description(self) -> str:
        return "Returns metadata about a file or directory (size, mtime, type)."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"], must_exist=True)
            st = path.stat()
            info = {
                "path": arguments["path"],
                "type": "dir" if path.is_dir() else "file",
                "size": st.st_size,
                "mtime": st.st_mtime,
                "mode": oct(st.st_mode),
            }
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output=info,
                human_readable=str(info),
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")




class SearchCodeTool(FileSystemToolBase):
    """Recursive text search across the workspace (find definitions/usages)."""

    def __init__(self, workspace: pathlib.Path):
        super().__init__(workspace)
        self.cfg_max_matches = 50
        self.cfg_max_file_size = 1_000_000

    @property
    def tool_id(self) -> str:
        return "fs_search_code"

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return (
            "Search for a text/pattern recursively in project files. "
            "Use to find where a function/class/symbol is defined or used. "
            "Returns file paths with line numbers and a short snippet."
        )

    @property
    def category(self) -> str:
        return "filesystem"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text or simple substring to find"},
                "path": {"type": "string", "description": "Subdirectory relative to workspace", "default": "."},
                "max_matches": {"type": "integer", "default": 50},
                "glob": {"type": "string", "description": "Optional filename filter e.g. *.py", "default": "*"},
            },
            "required": ["query"],
        }

    def settings_schema(self):
        from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="max_matches", label="Max matches", type=SettingType.INT, default=50, minimum=1, maximum=500),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if values and "max_matches" in values:
            self.cfg_max_matches = int(values["max_matches"])

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        query = (arguments.get("query") or "").strip()
        if not query:
            return self._create_error_result(call_id, "query is required", "INVALID_ARGS")
        root_rel = arguments.get("path") or "."
        max_matches = int(arguments.get("max_matches") or self.cfg_max_matches)
        glob_pat = arguments.get("glob") or "*"
        try:
            root = self._safe_path(root_rel, must_exist=True)
            if root.is_file():
                files = [root]
            else:
                files = [f for f in root.rglob(glob_pat) if f.is_file()]
            matches = []
            skip_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".exe", ".dll", ".so", ".bin", ".pyc", ".zip", ".gz"}
            for fp in files:
                if len(matches) >= max_matches:
                    break
                if fp.suffix.lower() in skip_ext:
                    continue
                try:
                    if fp.stat().st_size > self.cfg_max_file_size:
                        continue
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                try:
                    rel = str(fp.relative_to(self.workspace)).replace("\\\\", "/")
                except Exception:
                    rel = str(fp)
                for i, line in enumerate(text.splitlines(), 1):
                    if query in line:
                        matches.append({"path": rel, "line": i, "snippet": line.strip()[:200]})
                        if len(matches) >= max_matches:
                            break
            hr_lines = [f"{m['path']}:{m['line']}: {m['snippet']}" for m in matches]
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                success=True,
                stop_reason="completed",
                output={"matches": matches, "count": len(matches), "query": query},
                human_readable=(f"Found {len(matches)} match(es) for {query!r}:\\n" + "\\n".join(hr_lines)) if matches else f"No matches for {query!r}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class FileSystemTools:
    def __init__(self, workspace: str):
        self.workspace = pathlib.Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._tools: List[Tool] = [
            FileExistsTool(self.workspace),
            ReadFileTool(self.workspace),
            WriteFileTool(self.workspace),
            CreateFileTool(self.workspace),
            EditFileTool(self.workspace),
            DeleteFileTool(self.workspace),
            CreateDirectoryTool(self.workspace),
            ListDirectoryTool(self.workspace),
            GetFileInfoTool(self.workspace),
            SearchCodeTool(self.workspace),
        ]

    def get_tools(self) -> List[Tool]:
        return list(self._tools)
