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
from .models.router import ModelRouter
from .interfaces.errors import ProviderError, ErrorCode
from .tools.registry import ToolRegistry
from .tools.settings import ToolSettingsStore
from .security.policy import SecurityPolicy
from .assembly import build_tool_registry
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
        self.router = ModelRouter(list(self.providers.values()))

    def _load_config(self, config_path: Optional[Path]) -> PlatformConfig:
        return SettingsProvider(config_path).config

    def _merge_tool_config(self) -> None:
        """Seed tool toggles from the platform config only when tools.json is new."""
        from .settings.file import TOOLS_FILE, read_state_file

        raw = read_state_file(self.config.storage.state_dir, TOOLS_FILE)
        if any(key in raw for key in ("fs_enabled", "terminal_enabled", "enabled_tools")):
            self.tool_settings.load()
            return
        tc = self.config.tools
        self.tool_settings.update(
            fs_enabled=tc.fs_enabled,
            terminal_enabled=tc.terminal_enabled,
            web_search_enabled=tc.web_search_enabled,
            fetch_url_enabled=tc.fetch_url_enabled,
        )

    def _setup_storage(self) -> Storage:
        from Kerniq.devtools.paths import anchored_dir

        return JsonStorage(anchored_dir(self.config.storage.sessions_dir))

    def _setup_tools(self) -> None:
        workspace = Path(self.config.application.workspace_root)
        self.tool_registry, self.security_policy = build_tool_registry(
            workspace,
            config=self.config,
            state_dir=self.config.storage.state_dir,
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
        try:
            return self.router.select_provider(preferred_provider_id=provider_id)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc

    async def resolve_default_provider(self, *, allow_fallback: bool = False) -> ModelProvider:
        """Return the configured provider.

        LM Studio is not replaced by mock unless allow_fallback is explicitly
        True. A missing provider is an error.
        """
        preferred = self.config.models.default_provider
        provider = self.get_provider(preferred)
        if preferred in ("lm_studio",) or provider.provider_id == "lm_studio":
            if not await provider.check_connection():
                if allow_fallback and "mock" in self.providers:
                    logger.warning(
                        "LM Studio unreachable; using mock because allow_fallback=True"
                    )
                    return self.providers["mock"]
                raise ProviderError(
                    ErrorCode.PROVIDER_UNAVAILABLE,
                    "LM Studio is not reachable and silent fallback is disabled. "
                    "Start LM Studio or select the mock provider explicitly.",
                )
        return provider

    async def shutdown(self) -> None:
        await self.storage.close()
