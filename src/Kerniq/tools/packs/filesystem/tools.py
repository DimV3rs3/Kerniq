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


_OFFICE_SUFFIXES = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}


def _office_refusal(path: pathlib.Path) -> str | None:
    if path.suffix.lower() not in _OFFICE_SUFFIXES:
        return None
    return (
        f"{path.name} is an Office document, not plain text. "
        "create_file, write_file, edit_file, and read_file do not create or change it. "
        "Use office_create, office_read, and office_edit."
    )


class FileSystemToolBase(Tool):
    _PLAN_NAMES = frozenset({
        "file_exists",
        "read_file",
        "list_directory",
        "get_file_info",
        "search_code",
        "view_image",
    })

    def __init__(self, workspace: pathlib.Path):
        self.workspace = pathlib.Path(workspace).resolve()
        self._cfg_keys: tuple = ()
        self.cfg_auto_accept = False
        self.cfg_collapsible = True

    def plan_membership_default(self) -> bool:
        """Read and search stay in Plan. Writes and archives do not."""
        try:
            name = self.name
        except Exception:
            return False
        return name in self._PLAN_NAMES

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

    @property
    def display_phrase(self) -> str:
        phrases = {
            "file_exists": "existence checks",
            "read_file": "files read",
            "write_file": "files written",
            "create_file": "files created",
            "edit_file": "files edited",
            "delete_file": "files deleted",
            "create_directory": "dirs created",
            "list_directory": "dirs listed",
            "get_file_info": "info reads",
            "search_code": "code searches",
            "view_image": "images viewed",
            "zip": "archives packed",
            "unzip": "archives unpacked",
            "move_file": "files moved",
        }
        return phrases.get(self.name, "file operations")

    def settings_schema(self) -> SettingsSchema | None:
        from Kerniq.interfaces.settings_schema import SettingField, SettingType
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="include_in_plan",
                    label="Include in Plan mode",
                    type=SettingType.BOOL,
                    default=self.plan_membership_default(),
                    description="Allow this tool to be offered in Plan mode. "
                               "When on, the orchestrator may call this tool "
                               "according to its plan settings.",
                ),
            ],
        )

    def apply_settings(self, values: dict) -> None:
        values = values or {}
        if "include_in_plan" in values:
            self.cfg_include_in_plan = bool(values["include_in_plan"])
        for k, v in values.items():
            if k == "include_in_plan":
                continue
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

    def _match_external(self, target: pathlib.Path) -> tuple[pathlib.Path | None, bool]:
        """An attached file or directory that contains ``target``, plus the read-only flag."""
        task = current_task()
        meta = getattr(task, "metadata", None) or {} if task is not None else {}
        read_only = bool(meta.get("external_read_only", True))
        for item in meta.get("external_files") or []:
            try:
                root = pathlib.Path(str(item)).resolve()
            except OSError:
                continue
            try:
                inside = target == root or target.is_relative_to(root)
            except (OSError, ValueError):
                inside = False
            if inside:
                return root, read_only
        return None, read_only

    def _host_freedom(self) -> bool:
        return bool(getattr(getattr(self, "_security_policy", None), "host_freedom", False))

    def _shown_path(self, path: pathlib.Path) -> str | None:
        if self._host_freedom():
            try:
                return str(path.resolve())
            except OSError:
                return str(path)
        from Kerniq.server.homes import display_path, jail_root

        if jail_root() is not None:
            return display_path(path)
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        try:
            rel = resolved.relative_to(self.workspace).as_posix()
        except ValueError:
            root, _read_only = self._match_external(resolved)
            if root is None:
                return None
            from Kerniq.security.pathmask import VIRT_ATTACHMENTS, attachment_aliases

            for virtual, real in attachment_aliases().items():
                try:
                    real_path = pathlib.Path(real).resolve()
                    if resolved == real_path or resolved.is_relative_to(real_path):
                        extra = resolved.relative_to(real_path).as_posix()
                        return virtual if extra in ("", ".") else virtual.rstrip("/") + "/" + extra
                except (OSError, ValueError):
                    continue
            return VIRT_ATTACHMENTS + "/" + resolved.name
        if rel in ("", "."):
            return "./workspace"
        return "./workspace/" + rel

    def _admit(self, path: pathlib.Path, payload: str | bytes) -> None:
        from Kerniq.server.homes import admit_bytes, jail_root

        if jail_root() is None:
            return
        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        old = 0
        try:
            if path.is_file() and not path.is_symlink():
                old = path.stat().st_size
        except OSError:
            old = 0
        reason = admit_bytes(len(raw), old)
        if reason:
            raise PermissionError(reason)

    def _safe_path(self, path_str: str, *, must_exist: bool = False, write: bool | None = None) -> pathlib.Path:
        from Kerniq.server.homes import jail_root, logical_path

        jail = jail_root()
        if jail is not None:
            try:
                target = logical_path(str(path_str), jail)
            except PermissionError as exc:
                raise PermissionError("Access denied: that path is outside ./workspace") from exc
            writing = self.name in {
                "write_file", "create_file", "edit_file", "delete_file", "create_directory",
                "move_file",
            } if write is None else bool(write)
            if writing:
                from Kerniq.server.homes import write_blocked_reason

                blocked = write_blocked_reason()
                if blocked:
                    raise PermissionError(blocked)
            rel = target.relative_to(jail).as_posix()
            if rel not in ("", "."):
                blocked = strict_allows(rel, current_task())
                if blocked:
                    raise PermissionError(blocked)
            if must_exist and not target.exists():
                raise FileNotFoundError(f"File not found: {path_str}")
            return target
        raw = str(path_str)
        if "\x00" in raw or raw.startswith("\\\\") or raw.startswith("//"):
            raise PermissionError("Access denied: path is outside ./workspace")
        from Kerniq.security.pathmask import rewrite_model_path

        raw = rewrite_model_path(raw)
        base = self.workspace
        candidate = pathlib.Path(raw)
        writing = self.name in {
            "write_file", "create_file", "edit_file", "delete_file", "create_directory",
        } if write is None else bool(write)
        # An absolute path must not replace the workspace via Path.__truediv__.
        if candidate.is_absolute():
            target = candidate.resolve()
            if self._host_freedom():
                if writing:
                    from Kerniq.security.confinement import os_write_forbidden

                    blocked_os = os_write_forbidden(target)
                    if blocked_os:
                        raise PermissionError(blocked_os)
                if must_exist and not target.exists():
                    raise FileNotFoundError(f"File not found: {path_str}")
                return target
        else:
            target = (base / candidate).resolve()
        if writing:
            from Kerniq.server.homes import write_blocked_reason

            blocked = write_blocked_reason()
            if blocked:
                raise PermissionError(blocked)
        root, read_only = self._match_external(target)
        if root is not None:
            if writing and read_only:
                raise PermissionError("External attachments are read-only.")
            if must_exist and not target.exists():
                raise FileNotFoundError(f"File not found: {path_str}")
            return target
        if not target.is_relative_to(base):
            raise PermissionError("Access denied: path is outside ./workspace")
        blocked = strict_allows(target.relative_to(base).as_posix(), current_task())
        if blocked:
            raise PermissionError(blocked)
        if must_exist and not target.exists():
            raise FileNotFoundError(f"File not found: {path_str}")
        return target

    def _create_error_result(self, call_id: str, msg: str, error_code: str) -> ToolResult:
        text = msg
        if not self._host_freedom():
            from Kerniq.security.pathmask import scrub_for_model

            text = scrub_for_model(msg or "", workspace=self.workspace, reveal=False)
        return ToolResult(
            tool_call_id=call_id,
            tool_id=self.tool_id,
            status="error",
            output=None,
            human_readable=text,
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
    @property
    def display_phrase(self) -> str:
        return "files read"
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
            refused = _office_refusal(path)
            if refused:
                return self._create_error_result(call_id, refused, "FS_OFFICE")
            from Kerniq.models.vision import sniff_image

            head = path.read_bytes()[:32]
            if sniff_image(head):
                return ToolResult(
                    tool_call_id=call_id,
                    tool_id=self.tool_id,
                    status="success",
                    output={"image": True, "path": arguments["path"]},
                    human_readable=(
                        "This file is an image. The bytes were not returned. "
                        "Call view_image with this path to see the picture itself."
                    ),
                )
            max_bytes = int(arguments.get("max_bytes", self.cfg_max_bytes))
            data = path.read_bytes()
            truncated = len(data) > max_bytes
            if truncated:
                data = data[:max_bytes]
            content = data.decode("utf-8", errors="replace")
            note = "\n...[truncated]" if truncated else ""
            text = content + note
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"content": text, "truncated": truncated, "size": path.stat().st_size},
                human_readable=text,
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class ViewImageTool(FileSystemToolBase):
    @property
    def tool_id(self) -> str:
        return "fs_view_image"

    @property
    def name(self) -> str:
        return "view_image"

    @property
    def description(self) -> str:
        return (
            "Show one image file so you can see it. "
            "Use this for a photo or picture in the workspace, or for a file the user attached. "
            "The result is the picture itself, not a byte array and not a text dump. "
            "path is relative to the workspace. Do not use read_file on an image."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Workspace path of the image."}},
            "required": ["path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        from Kerniq.models.vision import MAX_IMAGE_BYTES, image_record, sniff_image

        call_id = arguments.get("tool_call_id", "unknown")
        try:
            path = self._safe_path(arguments["path"], must_exist=True)
            if not path.is_file():
                return self._create_error_result(call_id, f"Not a file: {arguments['path']}", "FS_ERROR")
            size = path.stat().st_size
            if size > MAX_IMAGE_BYTES:
                return self._create_error_result(
                    call_id,
                    "That image is larger than 6 MB, so it was not sent.",
                    "FS_ERROR",
                )
            if sniff_image(path.read_bytes()[:32]) is None:
                return self._create_error_result(
                    call_id,
                    "That file is not a PNG, JPEG, GIF, WEBP, or BMP image.",
                    "FS_ERROR",
                )
            try:
                root = self.workspace if path.is_relative_to(self.workspace) else path.parent
            except OSError:
                root = path.parent
            record = image_record(path, root)
            if record is None:
                return self._create_error_result(call_id, "The image could not be prepared.", "FS_ERROR")
            try:
                label = path.relative_to(self.workspace).as_posix()
            except ValueError:
                label = path.name
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": label, "mime": record["mime"], "bytes": size, "image": record},
                human_readable=(
                    f"Image loaded: {label} ({record['mime']}, {size} bytes). "
                    "The picture is attached for you to look at. Do not ask for the raw bytes."
                ),
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
        return "Creates or overwrites a text file. Office documents (.docx, .xlsx, .pptx, .odt, .ods, .odp and the legacy binaries) are refused."

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
            refused = _office_refusal(path)
            if refused:
                return self._create_error_result(call_id, refused, "FS_OFFICE")
            if arguments.get("create_dirs", True):
                path.parent.mkdir(parents=True, exist_ok=True)
            self._admit(path, arguments["content"])
            path.write_text(arguments["content"], encoding="utf-8")
            shown = self._shown_path(path) or arguments["path"]
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={"path": shown, "bytes": path.stat().st_size},
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
        return "Creates a new text file and fails if it already exists. It cannot create an Office document."

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
            refused = _office_refusal(path)
            if refused:
                return self._create_error_result(call_id, refused, "FS_OFFICE")
            if path.exists():
                return self._create_error_result(
                    call_id, f"File already exists: {arguments['path']}", "FS_EXISTS"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            self._admit(path, arguments.get("content", ""))
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
            "Edits an existing text file. Provide either (old_string + new_string) for "
            "search-replace, or content for a full overwrite. Office documents are refused: use office_edit."
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
            refused = _office_refusal(path)
            if refused:
                return self._create_error_result(call_id, refused, "FS_OFFICE")
            if not path.is_file():
                return self._create_error_result(call_id, f"Not a file: {arguments['path']}", "FS_ERROR")

            if "content" in arguments and arguments["content"] is not None and "old_string" not in arguments:
                self._admit(path, arguments["content"])
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
                    call_id, f"The text to replace was not found in {arguments['path']}.", "FS_NOT_FOUND"
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
            self._admit(path, updated)
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
    @property
    def display_phrase(self) -> str:
        return "dirs listed"
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
                    rel = self._shown_path(f)
                    if rel is None:
                        continue
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
                        rel = self._shown_path(item)
                        if rel is None:
                            continue
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

    @property
    def display_phrase(self) -> str:
        return "code searches"

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
                SettingField(key="collapsible", label="Merge consecutive calls in chat", type=SettingType.BOOL, default=True),
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
                files = []
                for found in root.rglob(glob_pat):
                    if not found.is_file():
                        continue
                    files.append(found)
                    if len(files) >= 4000:
                        break
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
            out = self._safe_path(archive_rel, write=True)
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
                dest = self._safe_path(dest_rel, write=True)
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
            src = self._safe_path(arguments["src"], must_exist=True, write=True)
            dst = self._safe_path(arguments["dst"], write=True)
            if dst == src:
                raise PermissionError("Source and destination are the same")
            if dst.is_relative_to(src):
                raise PermissionError("Cannot move a directory into itself")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            def _label(path: pathlib.Path) -> str:
                try:
                    return path.relative_to(self.workspace).as_posix()
                except ValueError:
                    return str(path)

            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success",
                output={
                    "src": _label(src),
                    "dst": _label(dst),
                },
                human_readable=f"Moved {arguments['src']} -> {arguments['dst']}",
            )
        except Exception as e:
            return self._create_error_result(call_id, str(e), "FS_ERROR")


class FileSystemTools:
    def __init__(self, workspace: str, policy: Any = None):
        self.workspace = pathlib.Path(workspace).resolve()
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
            ViewImageTool(self.workspace),
            ZipTool(self.workspace),
            UnzipTool(self.workspace),
            MoveFileTool(self.workspace),
        ]
        for tool in self._tools:
            tool._security_policy = policy

    def get_tools(self) -> List[Tool]:
        return list(self._tools)
