"""Context compaction — keep system + last N messages."""

from __future__ import annotations

from typing import Any, Dict, List

from agent_platform.plugins.base import Plugin, PluginContext
from agent_platform.plugins.manifest import PluginManifest
from agent_platform.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
from agent_platform.interfaces.models import Message, MessageRole


COMPACT_INSTRUCTION = (
    "Context is near the limit. Produce a compact summary of the conversation so far "
    "that preserves: goals, decisions, file paths touched, function/class signatures "
    "and key parameters, failed approaches, and open TODOs. "
    "Do NOT drop symbol names or file paths the agent still needs to call tools correctly."
)


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self.cfg_enabled = True
        self.cfg_trigger_percent = 75
        self.cfg_keep_last = 12
        self.cfg_max_tokens = 8000
        self._manifest = PluginManifest(
            plugin_id="plugin_context_compact",
            name="Context Compact",
            version="0.2.0",
            api_version="1.0",
            entry_point="main.PluginImpl",
            description="Compacts long conversation context",
            capabilities=["context"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def settings_schema(self):
        return SettingsSchema(
            component_id="plugin_context_compact",
            component_type="plugin",
            title="Context Compact",
            fields=[
                SettingField(key="enabled", label="Enabled", type=SettingType.BOOL, default=True),
                SettingField(key="trigger_percent", label="Trigger at fill %", type=SettingType.INT, default=75, minimum=10, maximum=100),
                SettingField(key="keep_last", label="Keep last N messages", type=SettingType.INT, default=12, minimum=2, maximum=200),
                SettingField(key="max_tokens", label="Max context tokens (approx)", type=SettingType.INT, default=8000, minimum=512, maximum=200000),
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if not values:
            return
        if "enabled" in values:
            self.cfg_enabled = bool(values["enabled"])
        if "trigger_percent" in values:
            self.cfg_trigger_percent = int(values["trigger_percent"])
        if "keep_last" in values:
            self.cfg_keep_last = int(values["keep_last"])
        if "max_tokens" in values:
            self.cfg_max_tokens = int(values["max_tokens"])

    def estimate_tokens(self, messages: List[Message]) -> int:
        total = sum(len(m.content or "") for m in messages)
        return max(1, total // 4)

    def needs_compact(self, messages: List[Message]) -> bool:
        if not self.cfg_enabled:
            return False
        est = self.estimate_tokens(messages)
        return est * 100 >= self.cfg_max_tokens * self.cfg_trigger_percent

    def compact(self, messages: List[Message], summary: str | None = None) -> List[Message]:
        if not self.cfg_enabled:
            return messages
        systems = [m for m in messages if m.role == MessageRole.SYSTEM]
        rest = [m for m in messages if m.role != MessageRole.SYSTEM]
        if len(rest) <= self.cfg_keep_last and not summary:
            return messages
        tail = rest[-self.cfg_keep_last :]
        mid = Message(
            role=MessageRole.SYSTEM,
            content=summary
            or (
                COMPACT_INSTRUCTION
                + f"\n\n[context compacted: {max(0, len(rest) - self.cfg_keep_last)} messages omitted]"
            ),
        )
        return systems + [mid] + tail

    async def initialize(self, context: PluginContext) -> bool:
        if context.logger:
            context.logger.info(
                "Context compact ready (trigger=%s%% max_tokens=%s keep_last=%s)",
                self.cfg_trigger_percent,
                self.cfg_max_tokens,
                self.cfg_keep_last,
            )
        return True

    async def shutdown(self) -> None:
        pass
