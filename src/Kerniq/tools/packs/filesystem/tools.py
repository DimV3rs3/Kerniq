"""Filesystem tools with workspace boundary enforcement."""

from __future__ import annotations

from typing import Dict, Any, List
import pathlib
import os
import shutil

from ....interfaces.tools import Tool, ToolResult
from ....interfaces.settings_schema import SettingsSchema, SettingField, SettingType
from ....security.task_scope import current_task, strict_allows

def _collapse_field() -> SettingField:
    return SettingField(
        key="collapsible",
        label="Merge consecutive calls in chat",
        type=SettingType.BOOL,
        default=True,
        description="Merge consecutive calls of this tool into one chat block when aggregation is on",
    )

def _ensure_collapse(schema: SettingsSchema | None, tool_id: str, title: str) -> SettingsSchema:
    if schema is None:
        schema = SettingsSchema(component_id=tool_id, component_type="tool", title=title, fields=[])
    if not any(f.key == "collapsible" for f in schema.fields):
        schema.fields.append(_collapse_field())
    return schema


class FileSystemToolBase(Tool):
    def __init__(self, workspace: pathlib.Path):
        self.workspace = pathlib.Path(workspace).resolve()
        self._cfg_keys: tuple = ()
        self.cfg_auto_accept = False
        self.cfg_collapsible = True

    @property
    def category(self) -> str:
        return "filesystem"

    @property
    def pack_id(self) -> str:
        return "filesystem"

    @property
    def ui_icon(self) -> str:
        return "📄"

    @property
    def collapsible(self) -> bool:
        return bool(getattr(self, "cfg_collapsible", True))

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} файловых операций"

    def settings_schema(self) -> SettingsSchema | None:
        return None

    def apply_settings(self, values: dict) -> None:
        for k, v in (values or {}).items():
            attr = f"cfg_{k}"
            if hasattr(self, attr) or k in getattr(self, "_cfg_keys", ()):
                setattr(self, attr, v)

    @property
    def risk_level(self) -> str:
        name = ""
        try:
            name = self.name
        except Exception:
            name = ""
        return {
            "delete_file": "high",
            "write_file": "medium",
            "create_file": "medium",
            "edit_file": "medium",
            "move_file": "medium",
            "unzip": "medium",
            "zip": "medium",
        }.get(name, "low")

    def _safe_path(self, path_str: str, *, must_exist: bool = False) -> pathlib.Path:
        raw = str(path_str)
        if "\x00" in raw or raw.startswith("\\\\") or raw.startswith("//"):
            raise PermissionError(f"Access denied: {path_str} is outside workspace")
        base = self.workspace
        candidate = pathlib.Path(raw)
        # An absolute path must not replace the workspace via Path.__truediv__.
        if candidate.is_absolute():
            target = candidate.resolve()
        else:
            target = (base / candidate).resolve()
        if not target.is_relative_to(base):
            raise PermissionError(f"Access denied: {path_str} is outside workspace")
        blocked = strict_allows(target.relative_to(base).as_posix(), current_task())
        if blocked:
            raise PermissionError(blocked)
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
    @property
    def ui_icon(self) -> str:
        return "📄"
    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} файлов прочитано"
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
            wrapped = (
                f'<untrusted_file_content path="{arguments["path"]}">\n'
                f"{content}{note}\n"
                "</untrusted_file_content>"
            )
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"content": wrapped, "truncated": truncated, "size": path.stat().st_size},
                human_readable=wrapped,
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class WriteFileTool(FileSystemToolBase):
    @property
    def ui_icon(self) -> str:
        return "✍️"
    @property
    def collapsible(self) -> bool:
        return False
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
    def ui_icon(self) -> str:
        return "🗑"
    @property
    def collapsible(self) -> bool:
        return False
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
    @property
    def ui_icon(self) -> str:
        return "📁"
    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} просмотров папок"
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
        self.cfg_collapsible = True

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
    def pack_id(self) -> str:
        return "filesystem"

    @property
    def ui_icon(self) -> str:
        return "🔎"

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} поисков по коду"

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
                SettingField(key="collapsible", label="Объединять вызовы в чате", type=SettingType.BOOL, default=True),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        if not values:
            return
        if "max_matches" in values:
            self.cfg_max_matches = int(values["max_matches"])
        if "collapsible" in values:
            self.cfg_collapsible = bool(values["collapsible"])

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



class ReadDocxTool(FileSystemToolBase):
    """Read a .docx file into structured text (paragraphs + tables)."""

    @property
    def tool_id(self) -> str:
        return "fs_read_docx"

    @property
    def name(self) -> str:
        return "read_docx"

    @property
    def description(self) -> str:
        return (
            "Read a Microsoft Word .docx file from the workspace. "
            "Returns paragraphs and tables as plain structured text."
        )

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Workspace-relative path to a .docx file"},
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate output after this many characters (default 100000)",
                },
            },
            "required": ["path"],
        }

    def _extract_docx(self, path) -> str:
        import zipfile
        import xml.etree.ElementTree as ET

        NS = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        }
        parts: list[str] = []
        with zipfile.ZipFile(path, "r") as zf:
            # main document
            xml = zf.read("word/document.xml")
            root = ET.fromstring(xml)
            for child in root.iter():
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "p":
                    texts = []
                    for node in child.iter():
                        nt = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                        if nt == "t" and node.text:
                            texts.append(node.text)
                        if nt == "tab":
                            texts.append("\t")
                    line = "".join(texts).strip()
                    if line:
                        parts.append(line)
                elif tag == "tbl":
                    parts.append("\n[Table]")
                    for row in child.iter():
                        rt = row.tag.split("}")[-1] if "}" in row.tag else row.tag
                        if rt != "tr":
                            continue
                        cells = []
                        for cell in row:
                            ct = cell.tag.split("}")[-1] if "}" in cell.tag else cell.tag
                            if ct != "tc":
                                continue
                            cell_texts = []
                            for node in cell.iter():
                                nt = node.tag.split("}")[-1] if "}" in node.tag else node.tag
                                if nt == "t" and node.text:
                                    cell_texts.append(node.text)
                            cells.append("".join(cell_texts).strip())
                        if any(cells):
                            parts.append(" | ".join(cells))
                    parts.append("[/Table]\n")
        return "\n".join(parts)

    async def execute(self, arguments, context):
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"])
            if not path.exists() or not path.is_file():
                return self._create_error_result(call_id, f"File not found: {arguments.get('path')}", "FS_NOT_FOUND")
            if path.suffix.lower() != ".docx":
                return self._create_error_result(
                    call_id,
                    "Not a .docx file (use read_file for plain text)",
                    "FS_BAD_TYPE",
                )
            text = self._extract_docx(path)
            max_chars = int(arguments.get("max_chars") or 100_000)
            truncated = False
            if len(text) > max_chars:
                text = text[:max_chars] + "\n…[truncated]"
                truncated = True
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": arguments["path"], "chars": len(text), "truncated": truncated, "text": text},
                human_readable=text if len(text) < 2000 else text[:2000] + "…",
            )
        except KeyError as e:
            return self._create_error_result(call_id, f"Invalid docx structure: {e}", "DOCX_ERROR")
        except Exception as e:
            return self._create_error_result(call_id, str(e), "DOCX_ERROR")



class ZipTool(FileSystemToolBase):
    """Create a zip archive from workspace files/dirs."""

    @property
    def tool_id(self) -> str:
        return "fs_zip"

    @property
    def name(self) -> str:
        return "zip"

    @property
    def description(self) -> str:
        return (
            "Create a .zip archive inside the workspace from one or more paths "
            "(files or directories). Does not use the terminal."
        )

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Workspace-relative paths to include",
                },
                "path": {
                    "type": "string",
                    "description": "Single path (alternative to paths)",
                },
                "archive": {
                    "type": "string",
                    "description": "Output .zip path relative to workspace (default: archive.zip)",
                },
            },
        }

    async def execute(self, arguments, context):
        import zipfile
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            paths = list(arguments.get("paths") or [])
            if arguments.get("path"):
                paths.append(arguments["path"])
            if not paths:
                return self._create_error_result(call_id, "Provide path or paths", "ZIP_ARGS")
            archive_rel = arguments.get("archive") or "archive.zip"
            if not str(archive_rel).lower().endswith(".zip"):
                archive_rel = str(archive_rel) + ".zip"
            out = self._safe_path(archive_rel)
            out.parent.mkdir(parents=True, exist_ok=True)
            added = []
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for rel in paths:
                    src = self._safe_path(rel, must_exist=True)
                    if src.is_file():
                        arcname = src.relative_to(self.workspace).as_posix()
                        zf.write(src, arcname)
                        added.append(arcname)
                    elif src.is_dir():
                        for f in src.rglob("*"):
                            if f.is_file():
                                arcname = f.relative_to(self.workspace).as_posix()
                                zf.write(f, arcname)
                                added.append(arcname)
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"archive": archive_rel, "files": len(added)},
                human_readable=f"Created {archive_rel} with {len(added)} file(s)",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "ZIP_ERROR")


class UnzipTool(FileSystemToolBase):
    """Extract a zip archive into the workspace."""

    @property
    def tool_id(self) -> str:
        return "fs_unzip"

    @property
    def name(self) -> str:
        return "unzip"

    @property
    def description(self) -> str:
        return (
            "Extract a .zip archive into the workspace (optional destination folder). "
            "Blocks path traversal. Does not use the terminal."
        )

    @property
    def input_schema(self):
        return {
            "type": "object",
            "properties": {
                "archive": {"type": "string", "description": "Workspace-relative .zip path"},
                "path": {"type": "string", "description": "Alias for archive"},
                "destination": {
                    "type": "string",
                    "description": "Folder to extract into (default: archive stem next to zip)",
                },
            },
            "required": [],
        }

    async def execute(self, arguments, context):
        import zipfile
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            arch_rel = arguments.get("archive") or arguments.get("path")
            if not arch_rel:
                return self._create_error_result(call_id, "Provide archive path", "UNZIP_ARGS")
            src = self._safe_path(arch_rel, must_exist=True)
            if src.suffix.lower() != ".zip":
                return self._create_error_result(call_id, "Not a .zip file", "UNZIP_TYPE")
            dest_rel = arguments.get("destination")
            if dest_rel:
                dest = self._safe_path(dest_rel)
            else:
                dest = src.with_suffix("")
            dest.mkdir(parents=True, exist_ok=True)
            extracted = []
            with zipfile.ZipFile(src, "r") as zf:
                for info in zf.infolist():
                    name = info.filename.replace("\\\\", "/").lstrip("/")
                    if ".." in name.split("/"):
                        continue
                    target = (dest / name).resolve()
                    if not target.is_relative_to(self.workspace.resolve()):
                        continue
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src_f, open(target, "wb") as out_f:
                        out_f.write(src_f.read())
                    extracted.append(target.relative_to(self.workspace).as_posix())
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"destination": str(dest.relative_to(self.workspace)), "files": len(extracted)},
                human_readable=f"Extracted {len(extracted)} file(s) to {dest.relative_to(self.workspace)}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "UNZIP_ERROR")


class MoveFileTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_move_file"

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return (
            "Move or rename a file or directory inside the workspace. "
            "Both paths are checked against the workspace root."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        call_id = arguments.get("tool_call_id", "unknown")
        try:
            src = self._safe_path(arguments["src"], must_exist=True)
            dst = self._safe_path(arguments["dst"])
            if dst == src:
                raise PermissionError("Source and destination are the same")
            if dst.is_relative_to(src):
                raise PermissionError("Cannot move a directory into itself")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={
                    "src": src.relative_to(self.workspace).as_posix(),
                    "dst": dst.relative_to(self.workspace).as_posix(),
                },
                human_readable=f"Moved {arguments['src']} -> {arguments['dst']}",
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
            ReadDocxTool(self.workspace),
            WriteFileTool(self.workspace),
            CreateFileTool(self.workspace),
            EditFileTool(self.workspace),
            DeleteFileTool(self.workspace),
            CreateDirectoryTool(self.workspace),
            ListDirectoryTool(self.workspace),
            GetFileInfoTool(self.workspace),
            SearchCodeTool(self.workspace),
            ZipTool(self.workspace),
            UnzipTool(self.workspace),
            MoveFileTool(self.workspace),
        ]

    def get_tools(self) -> List[Tool]:
        return list(self._tools)
