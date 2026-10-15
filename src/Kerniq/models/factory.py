"""Build a ModelProvider from the catalog plus UI/config values."""

from __future__ import annotations

from typing import Any, Optional

from ..interfaces.errors import ConfigurationError
from .catalog import spec_by_id
from .providers.anthropic import AnthropicProvider
from .providers.claude_code import ClaudeCodeProvider
from .providers.lm_studio import LMStudioProvider
from .providers.mock import MockProvider
from .providers.openai_compat import OpenAICompatProvider


def _dump(api: Any) -> dict:
    if api is None:
        return {}
    if hasattr(api, "model_dump"):
        return api.model_dump()
    if isinstance(api, dict):
        return dict(api)
    return {}


def build_provider(
    provider_id: str,
    *,
    api: Any = None,
    config: Any = None,
    timeout: float = 600.0,
):
    spec = spec_by_id(provider_id)
    if spec is None:
        raise ConfigurationError(f"Unknown provider '{provider_id}'")
    data = _dump(api)
    cfg_map: dict = {}
    if config is not None:
        providers = getattr(getattr(config, "models", None), "providers", None) or {}
        raw = providers.get(spec["id"]) if isinstance(providers, dict) else None
        if isinstance(raw, dict):
            cfg_map = raw
    field_keys = {f["key"] for f in spec.get("fields") or []}
    default_base = spec.get("default_base_url") or ""
    if "base_url" in field_keys:
        base = (data.get("base_url") or cfg_map.get("base_url") or default_base or "").rstrip("/")
    else:
        # Hidden field: do not reuse a stale LM Studio URL stored on the settings object.
        base = (cfg_map.get("base_url") or default_base or "").rstrip("/")
    token = data.get("api_token") or cfg_map.get("api_key") or cfg_map.get("api_token") or ""
    model = (data.get("model") or cfg_map.get("model") or "") or None
    if isinstance(model, str):
        model = model.strip() or None
    binary = (
        data.get("binary_path")
        or cfg_map.get("binary_path")
        or spec.get("default_binary")
        or "claude"
    )
    kind = spec["kind"]
    if kind == "mock":
        return MockProvider()
    if kind == "lm_studio":
        return LMStudioProvider(
            base_url=base or "http://127.0.0.1:1234",
            api_key=token or None,
            model=model,
            timeout=timeout,
        )
    if kind == "openai":
        return OpenAICompatProvider(
            provider_id=spec["id"],
            base_url=base,
            api_key=token or None,
            model=model,
            timeout=timeout,
            extra_headers=spec.get("headers") or None,
            label=spec["label"],
            requires_key="api_token" in field_keys,
        )
    if kind == "anthropic":
        return AnthropicProvider(
            api_key=token or None,
            model=model,
            base_url=base or "https://api.anthropic.com",
            timeout=timeout,
        )
    if kind == "claude_code":
        return ClaudeCodeProvider(binary_path=str(binary or "claude"), model=model, timeout=timeout)
    raise ConfigurationError(f"Unsupported provider kind '{kind}'")
