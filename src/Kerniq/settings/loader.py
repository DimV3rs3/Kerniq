"""Configuration loader using stdlib tomllib."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Optional

from .schema import PlatformConfig


class SettingsProvider:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            from Kerniq.devtools.paths import find_project_root

            root = find_project_root()
            config_path = (root / "config" / "default.toml") if root else Path("config/default.toml")
        self.config_path = config_path
        self._config: Optional[PlatformConfig] = None

    def load(self) -> PlatformConfig:
        if self._config is not None:
            return self._config
        data: dict = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "rb") as f:
                    data = tomllib.load(f)
            except Exception as e:
                raise RuntimeError(f"Error loading config {self.config_path}: {e}") from e
        env_provider = os.environ.get("AGENT_PLATFORM_DEFAULT_PROVIDER")
        if env_provider:
            data.setdefault("models", {})
            data["models"]["default_provider"] = env_provider
        self._config = PlatformConfig(**data)
        _anchor_install_paths(self._config)
        return self._config

    @property
    def config(self) -> PlatformConfig:
        return self.load()

    def reload(self) -> PlatformConfig:
        self._config = None
        return self.load()


def _anchor_install_paths(config: PlatformConfig) -> None:
    """Make install-relative paths absolute before anyone joins them to cwd."""
    from Kerniq.devtools.paths import anchored_dir

    config.storage.state_dir = anchored_dir(config.storage.state_dir)
    config.storage.sessions_dir = anchored_dir(config.storage.sessions_dir)
    config.application.workspace_root = anchored_dir(config.application.workspace_root)
    config.logging.log_file = anchored_dir(config.logging.log_file)