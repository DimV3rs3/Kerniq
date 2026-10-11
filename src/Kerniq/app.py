"""Application bootstrap and composition root."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict

from .settings.schema import PlatformConfig
from .settings.loader import SettingsProvider
from .interfaces.providers import ModelProvider
from .models.providers.mock import MockProvider
from .models.providers.lm_studio import LMStudioProvider
from .tools.registry import ToolRegistry
from .tools.filesystem import FileSystemTools
from .tools.terminal import TerminalTools
from .tools.web_search import WebSearchTool, FetchUrlTool
from .tools.settings import ToolSettingsStore
from .security.policy import SecurityPolicy
from .storage.json_store import JsonStorage
from .interfaces.storage import Storage
from .bootstrap import ensure_dependencies, format_bootstrap_report

logger = logging.getLogger(__name__)


class Application:
    def __init__(
        self,
        config_path: Optional[Path] = None,
        *,
        auto_install_deps: Optional[bool] = None,
    ):
        self.config = self._load_config(config_path)
        do_install = (
            self.config.application.auto_install_deps
            if auto_install_deps is None
            else auto_install_deps
        )
        self.bootstrap_report = ensure_dependencies(auto_install=do_install)
        if not self.bootstrap_report.ok:
            logger.warning(
                "Dependency issues:\n%s", format_bootstrap_report(self.bootstrap_report)
            )
        else:
            logger.info("Dependencies OK:\n%s", format_bootstrap_report(self.bootstrap_report))

        self.storage: Storage = self._setup_storage()
        self.tool_settings = ToolSettingsStore(self.config.storage.state_dir)
        self._merge_tool_config()
        self.tool_registry = ToolRegistry()
        self.security_policy: Optional[SecurityPolicy] = None
        self._setup_tools()
        self.providers: Dict[str, ModelProvider] = {}
        self._setup_providers()

    def _load_config(self, config_path: Optional[Path]) -> PlatformConfig:
        return SettingsProvider(config_path).config

    def _merge_tool_config(self) -> None:
        tc = self.config.tools
        self.tool_settings.update(
            fs_enabled=tc.fs_enabled,
            terminal_enabled=tc.terminal_enabled,
            web_search_enabled=tc.web_search_enabled,
            fetch_url_enabled=tc.fetch_url_enabled,
        )

    def _setup_storage(self) -> Storage:
        return JsonStorage(self.config.storage.sessions_dir)

    def _setup_tools(self) -> None:
        ts = self.tool_settings.settings
        workspace = Path(self.config.application.workspace_root)
        if ts.fs_enabled:
            for tool in FileSystemTools(workspace=str(workspace)).get_tools():
                self.tool_registry.register_tool(tool)
        policy = SecurityPolicy(
            workspace_root=workspace,
            disallowed_commands=self.config.security.disallowed_terminal_commands,
            require_approval_for_high_risk=self.config.security.require_approval_for_high_risk,
        )
        self.security_policy = policy
        if ts.terminal_enabled:
            self.tool_registry.register_tool(TerminalTools(workspace, policy))
        if ts.web_search_enabled:
            self.tool_registry.register_tool(
                WebSearchTool(
                    enabled=True,
                    max_results=ts.web_search_max_results,
                    timeout=ts.web_search_timeout,
                )
            )
        if ts.fetch_url_enabled:
            self.tool_registry.register_tool(
                FetchUrlTool(enabled=True, timeout=ts.fetch_url_timeout)
            )

    def _setup_providers(self) -> None:
        self.providers["mock"] = MockProvider()
        ls_cfg = self.config.models.providers.get("lm_studio", {})
        self.providers["lm_studio"] = LMStudioProvider(
            base_url=ls_cfg.get("base_url", "http://localhost:1234"),
            api_key=ls_cfg.get("api_key"),
            model=ls_cfg.get("model") or self.config.models.default_model or None,
            timeout=float(ls_cfg.get("timeout", self.config.runtime.timeout_seconds or 600)),
        )

    def get_provider(self, provider_id: str) -> ModelProvider:
        if provider_id not in self.providers:
            raise ValueError(f"Unknown provider: {provider_id}")
        return self.providers[provider_id]

    async def resolve_default_provider(self) -> ModelProvider:
        preferred = self.config.models.default_provider
        if preferred == "lm_studio":
            ls = self.providers["lm_studio"]
            if await ls.check_connection():
                return ls
            logger.warning("LM Studio unreachable; falling back to mock")
            return self.providers["mock"]
        return self.get_provider(preferred)

    async def shutdown(self) -> None:
        await self.storage.close()
