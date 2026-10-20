"""Tool contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel

from .settings_schema import SettingsSchema


class ToolResult(BaseModel):
    tool_call_id: str
    tool_id: str
    status: str  # "success", "error" (legacy)
    success: bool = True
    stop_reason: str = "completed"  # completed | timeout | denied | invalid_args | error | cancelled
    output: Any = None
    human_readable: str = ""
    error: Optional[str] = None
    duration_seconds: float = 0.0

    def model_post_init(self, __context: Any) -> None:
        # keep status/success in sync for older callers
        if self.status == "error":
            object.__setattr__(self, "success", False)
            if self.stop_reason == "completed":
                object.__setattr__(self, "stop_reason", "error")
        elif self.success is False and self.status == "success":
            object.__setattr__(self, "status", "error")

    def to_model_content(self) -> str:
        text = (self.human_readable or "").strip()
        if self.success:
            if text:
                return text
            if isinstance(self.output, str) and self.output.strip():
                body = self.output
                return body if len(body) < 8000 else body[:8000] + "..."
            return "Done."
        low = text.lower()
        code = (self.error or "").strip()
        if text.startswith(("Execution error:", "External error:", "File not found", "File already exists", "The text to replace")):
            return text
        if self.stop_reason == "timeout" or "timed out" in low or "timeout" in low:
            return "External error: the tool timed out. " + (text or code)
        if "already exist" in low:
            return text
        if "text to replace" in low or "was not found in" in low:
            return text or "The text to replace was not found."
        if isinstance(self.error, str) and "NOT_FOUND" in self.error.upper() or "not found" in low:
            if text.lower().startswith("file not found"):
                return text
            return "File not found. " + (text or code)
        if self.stop_reason == "denied" or "permission" in low or "access denied" in low:
            return "Execution error: permission denied. " + (text or code)
        if text:
            return "Execution error: " + text
        return "Execution error: the tool failed." + ((" " + code) if code else "")


class Tool(ABC):
    @property
    @abstractmethod
    def tool_id(self) -> str:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        pass

    @property
    def risk_level(self) -> str:
        """Trusted risk floor. The model cannot lower this at call time."""
        return "medium"

    @property
    def auto_accept(self) -> bool:
        """Per-tool opt-out of confirmation. Ignored when risk is critical."""
        return bool(getattr(self, "cfg_auto_accept", False))

    def plan_membership_default(self) -> bool:
        """Code default for Plan mode, before a saved setting.

        A tool sets ``_include_in_plan``. Otherwise it inherits
        ``_pack_include_in_plan`` copied from its pack at load time.
        Both missing means the tool stays out of Plan.
        """
        own = self.__dict__.get("_include_in_plan", None)
        if own is not None:
            return bool(own)
        pack = self.__dict__.get("_pack_include_in_plan", None)
        if pack is not None:
            return bool(pack)
        return True

    @property
    def include_in_plan(self) -> bool:
        """Whether Plan mode may offer this tool. A saved setting wins over the code default.

        ``update_plan`` is always offered in Plan mode, even when this is false.
        """
        saved = self.__dict__.get("cfg_include_in_plan", None)
        if saved is not None:
            return bool(saved)
        return self.plan_membership_default()

    @property
    def category(self) -> str:
        """Logical group for UI: filesystem | terminal | web | fetch | other."""
        return "other"

    @property
    def pack_id(self) -> str:
        """Owning tool pack id (folder-based pack)."""
        return self.category or "other"

    @property
    def ui_icon(self) -> str:
        """Emoji/icon for chat UI."""
        return "tool"


    @property
    def display_phrase(self) -> str:
        """English words shown after the call count, for example 'files read'.

        Kerniq reads this and passes it to whoever is displaying the call.
        Tools do not know about a shell, and they do not ship translations.
        """
        return "calls"

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        """Count plus the tool's own display phrase. English only."""
        phrase = self.display_phrase or "calls"
        if not success:
            return f"{count} {phrase} failed"
        return f"{count} {phrase}"

    def settings_schema(self) -> Optional[SettingsSchema]:
        """Default schema includes chat-collapse toggle; subclasses may extend."""
        from .settings_schema import SettingField, SettingType
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="collapsible",
                    label="Merge consecutive calls in chat",
                    type=SettingType.BOOL,
                    default=True,
                    description="When chat aggregation is on, consecutive calls of this tool merge into one block",
                ),
                SettingField(
                    key="auto_accept",
                    label="Auto-accept this tool",
                    type=SettingType.BOOL,
                    default=False,
                    description="Skip confirmation for this tool. Critical risk still always asks the user.",
                ),
                SettingField(
                    key="include_in_plan",
                    label="Include in Plan mode",
                    type=SettingType.BOOL,
                    default=self.plan_membership_default(),
                    description="Plan mode may call this tool. Writes, commands, and other changes stay off until this is on.",
                ),
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if values and "collapsible" in values:
            self.cfg_collapsible = bool(values["collapsible"])
        if values and "auto_accept" in values:
            self.cfg_auto_accept = bool(values["auto_accept"])
        if values and "include_in_plan" in values:
            self.cfg_include_in_plan = bool(values["include_in_plan"])

    @property
    def collapsible(self) -> bool:
        return bool(getattr(self, "cfg_collapsible", True))

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        return True
