"""Plan tool pack. Discovered with the other packs — not imported by CLI main."""

from __future__ import annotations

from typing import Any, Sequence

from ...pack import ToolPack, pack_resources_dir
from ....interfaces.tools import Tool
from .tools import UpdatePlanTool


class Pack(ToolPack):
    @property
    def pack_id(self) -> str:
        return "plan"

    @property
    def name(self) -> str:
        return "Plan"

    @property
    def description(self) -> str:
        return "Update the visible TODO plan"

    @property
    def category(self) -> str:
        return "plan"

    def resources_dir(self):
        return pack_resources_dir(__file__)

    def create_tools(self, workspace: str, **kwargs: Any) -> Sequence[Tool]:
        del workspace, kwargs
        return [UpdatePlanTool()]
