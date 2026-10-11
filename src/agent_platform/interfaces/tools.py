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

    def settings_schema(self) -> Optional[SettingsSchema]:
        """Optional declarative settings for UI/CLI. None = no extra settings."""
        return None

    def apply_settings(self, values: Dict[str, Any]) -> None:
        """Apply persisted settings into the tool instance."""
        return None

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        pass

    def validate_arguments(self, arguments: Dict[str, Any]) -> bool:
        return True
