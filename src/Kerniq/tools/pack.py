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

    def resources_dir(self) -> Optional[Path]:
        """Path to ``resources/`` next to the pack module, if present."""
        return None

    def settings_schema(self) -> Optional[SettingsSchema]:
        """Optional pack-level settings (applied to all tools or the pack itself)."""
        return None

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
        }


def pack_resources_dir(pack_file: str | Path) -> Path:
    """``resources/`` sibling of a pack ``__init__.py`` / ``tools.py``."""
    return Path(pack_file).resolve().parent / "resources"
