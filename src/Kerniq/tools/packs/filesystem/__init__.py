"""Filesystem tool pack."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ...pack import ToolPack, pack_resources_dir
from ....interfaces.tools import Tool
from .tools import FileSystemTools


class Pack(ToolPack):
    @property
    def pack_id(self) -> str:
        return "filesystem"

    @property
    def name(self) -> str:
        return "Filesystem"

    @property
    def description(self) -> str:
        return "Workspace-scoped file operations and code search"

    @property
    def category(self) -> str:
        return "filesystem"

    @property
    def include_in_plan(self) -> bool:
        return False

    def resources_dir(self):
        return pack_resources_dir(__file__)

    def create_tools(self, workspace: str, **kwargs: Any) -> Sequence[Tool]:
        return FileSystemTools(workspace, policy=kwargs.get("policy")).get_tools()
