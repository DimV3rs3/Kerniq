"""Terminal tool pack (PowerShell on Windows, bash on Unix)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ...pack import ToolPack, pack_resources_dir
from ....interfaces.tools import Tool
from ....security.policy import SecurityPolicy
from .tools import TerminalTools


class Pack(ToolPack):
    @property
    def pack_id(self) -> str:
        return "terminal"

    @property
    def name(self) -> str:
        return "Terminal"

    @property
    def description(self) -> str:
        return "Run shell commands inside the workspace (PowerShell on Windows)"

    @property
    def category(self) -> str:
        return "terminal"

    def resources_dir(self):
        return pack_resources_dir(__file__)

    def create_tools(self, workspace: str, **kwargs: Any) -> Sequence[Tool]:
        policy = kwargs.get("policy")
        if policy is None:
            policy = SecurityPolicy(workspace_root=Path(workspace))
        return [TerminalTools(Path(workspace), policy)]
