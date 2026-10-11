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
        """Compact JSON for the model (no Python tracebacks)."""
        import json
        payload = {
            "success": self.success,
            "stop_reason": self.stop_reason,
            "tool": self.tool_id,
            "error": self.error,
            "output": self.output if not isinstance(self.output, str) or len(self.output) < 8000 else self.output[:8000] + "…",
        }
        return json.dumps(payload, ensure_ascii=False)


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
        return "⚙"


    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        """Human label for chat aggregation, e.g. '3 поисков по коду'."""
        unit = "вызов" if count == 1 else "вызовов"
        return f"{count} {unit}"

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
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if values and "collapsible" in values:
            self.cfg_collapsible = bool(values["collapsible"])

    @property
    def collapsible(self) -> bool:
        return bool(getattr(self, "cfg_collapsible", True))

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        return True
