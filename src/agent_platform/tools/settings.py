"""Persistent tool settings (enabled flags, limits, search options)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolSettings(BaseModel):
    """Per-tool and global tool configuration that survives restarts."""

    # Global
    max_tool_output_chars: int = 50_000

    # Filesystem
    fs_enabled: bool = True
    fs_max_read_bytes: int = 200_000
    fs_list_max_entries: int = 500
    fs_list_max_depth: int = 5

    # Terminal
    terminal_enabled: bool = True
    terminal_default_timeout: int = 30
    terminal_max_output_chars: int = 50_000

    # Web
    web_search_enabled: bool = True
    web_search_max_results: int = 5
    web_search_timeout: float = 20.0
    fetch_url_enabled: bool = True
    fetch_url_timeout: float = 20.0
    fetch_url_max_bytes: int = 100_000

    # Explicit allow/deny by tool name (empty = all registered tools allowed by name)
    enabled_tools: Dict[str, bool] = Field(default_factory=dict)

    def is_tool_enabled(self, name: str) -> bool:
        if name in self.enabled_tools:
            return bool(self.enabled_tools[name])
        # Fallbacks by category
        if name in (
            "read_file",
            "write_file",
            "create_file",
            "edit_file",
            "delete_file",
            "list_directory",
            "file_exists",
            "create_directory",
            "get_file_info",
        ):
            return self.fs_enabled
        if name == "run_command":
            return self.terminal_enabled
        if name == "web_search":
            return self.web_search_enabled
        if name == "fetch_url":
            return self.fetch_url_enabled
        return True


class ToolSettingsStore:
    """Load/save ToolSettings as JSON under state_dir."""

    FILENAME = "tool_settings.json"

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / self.FILENAME
        self._settings: Optional[ToolSettings] = None

    def load(self) -> ToolSettings:
        if self._settings is not None:
            return self._settings
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._settings = ToolSettings(**data)
                return self._settings
            except Exception as e:
                logger.warning("Failed to load tool settings, using defaults: %s", e)
        self._settings = ToolSettings()
        return self._settings

    def save(self, settings: Optional[ToolSettings] = None) -> None:
        if settings is not None:
            self._settings = settings
        if self._settings is None:
            self._settings = ToolSettings()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(self._settings.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def settings(self) -> ToolSettings:
        return self.load()

    def update(self, **kwargs: Any) -> ToolSettings:
        current = self.load().model_dump()
        current.update(kwargs)
        self._settings = ToolSettings(**current)
        self.save()
        return self._settings
