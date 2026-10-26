"""Tool pack contract — folder-based, portable tool groups."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..interfaces.tools import Tool
from ..interfaces.settings_schema import SettingsSchema, SettingField, SettingType


class ToolPack(ABC):
    """A relocatable folder of related tools + optional resources."""

    @property
    @abstractmethod
    def pack_id(self) -> str:
        """Stable id, e.g. ``filesystem``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable pack name."""

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return ""

    @property
    def category(self) -> str:
        """Default category for tools in this pack."""
        return self.pack_id

    @property
    def include_in_plan(self) -> bool:
        """Default Plan-mode membership for tools that do not choose themselves.

        False keeps a new pack out of Plan. A tool's own flag, then a saved
        per-tool setting, both win over this.
        """
        return False

    def resources_dir(self) -> Optional[Path]:
        """Path to ``resources/`` next to the pack module, if present."""
        return None

    def settings_schema(self) -> Optional[SettingsSchema]:
        """Pack-level switches. The UI renders these fields; it does not invent them.

        Applying a field writes it onto every tool in the pack. A single tool
        can still override the same key afterwards.
        """
        return SettingsSchema(
            component_id=self.pack_id,
            component_type="pack",
            title=self.name,
            fields=[
                SettingField(
                    key="include_in_plan",
                    label="Include this pack in Plan mode",
                    type=SettingType.BOOL,
                    default=bool(self.include_in_plan),
                    description=(
                        "Plan mode may call the tools in this pack. "
                        "A tool can still opt out on its own settings."
                    ),
                ),
                SettingField(
                    key="auto_accept",
                    label="Auto-accept every tool in this pack",
                    type=SettingType.BOOL,
                    default=False,
                    description="Skip confirmation for every tool in this pack. Critical risk still always asks.",
                ),
                SettingField(
                    key="collapsible",
                    label="Merge calls for every tool in this pack",
                    type=SettingType.BOOL,
                    default=True,
                    description="Consecutive calls of these tools merge into one chat block.",
                ),
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        return None

    @abstractmethod
    def create_tools(self, workspace: str, **kwargs: Any) -> Sequence[Tool]:
        """Instantiate tools for this pack (workspace-aware)."""

    def manifest_dict(self) -> Dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "include_in_plan": bool(self.include_in_plan),
        }


def pack_resources_dir(pack_file: str | Path) -> Path:
    """``resources/`` sibling of a pack ``__init__.py`` / ``tools.py``."""
    return Path(pack_file).resolve().parent / "resources"
