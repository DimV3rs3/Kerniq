"""Deterministic provider selection.

A requested provider that is not registered is an error. Capability filters
do not silently fall through to an unrelated provider.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..interfaces.providers import ModelProvider

# Public ids used by config/CLI versus the id some adapters report.
_ALIASES = {
    "mock": "mock_provider",
    "mock_provider": "mock",
}


def _matches(provider: ModelProvider, wanted: str) -> bool:
    pid = provider.provider_id
    return pid == wanted or _ALIASES.get(wanted) == pid or _ALIASES.get(pid) == wanted


class ModelRouter:
    def __init__(self, providers: List[ModelProvider]):
        self.providers = list(providers)

    def select_provider(
        self,
        required_capabilities: Optional[List[str]] = None,
        preferred_provider_id: Optional[str] = None,
    ) -> ModelProvider:
        if preferred_provider_id:
            for provider in self.providers:
                if _matches(provider, preferred_provider_id):
                    return provider
            known = [p.provider_id for p in self.providers]
            raise RuntimeError(
                f"Requested provider '{preferred_provider_id}' is not registered "
                f"(available: {known or 'none'})"
            )

        if required_capabilities:
            matched = []
            for provider in self.providers:
                caps: Dict[str, object] = provider.get_capabilities() or {}
                if all(bool(caps.get(cap, False)) for cap in required_capabilities):
                    matched.append(provider)
            if not matched:
                raise RuntimeError(
                    "No registered provider supports capabilities: "
                    + ", ".join(required_capabilities)
                )
            return matched[0]

        if not self.providers:
            raise RuntimeError("No model providers registered")
        return self.providers[0]
