"""Security policy engine for tool execution and workspace access."""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..interfaces.errors import SecurityError, ErrorCode


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class SecurityPolicy:
    def __init__(
        self,
        workspace_root: Path,
        disallowed_commands: Optional[List[str]] = None,
        require_approval_for_high_risk: bool = True,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.disallowed_commands = disallowed_commands or []
        self.require_approval_for_high_risk = require_approval_for_high_risk

    def validate_path(self, path: str) -> Path:
        try:
            p = Path(path)
            if not p.is_absolute():
                p = (self.workspace_root / p).resolve()
            else:
                p = p.resolve()
            try:
                p.relative_to(self.workspace_root)
            except ValueError as exc:
                raise SecurityError(
                    ErrorCode.PERMISSION_DENIED,
                    f"Path {path} is outside the workspace root {self.workspace_root}",
                ) from exc
            return p
        except SecurityError:
            raise
        except Exception as e:
            raise SecurityError(
                ErrorCode.PERMISSION_DENIED, f"Invalid path: {path}. Error: {e}"
            ) from e

    def evaluate_tool_call(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel | str = RiskLevel.MEDIUM,
    ) -> PolicyDecision:
        if isinstance(risk_level, str):
            try:
                risk_level = RiskLevel(risk_level)
            except ValueError:
                risk_level = RiskLevel.MEDIUM

        if tool_id in ("run_command", "terminal"):
            cmd = arguments.get("command", "")
            for forbidden in self.disallowed_commands:
                if forbidden in cmd:
                    return PolicyDecision.DENY

        if risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            if self.require_approval_for_high_risk:
                return PolicyDecision.REQUIRE_APPROVAL
        return PolicyDecision.ALLOW

    def check_terminal_command(self, command: str) -> PolicyDecision:
        for forbidden in self.disallowed_commands:
            if forbidden in command:
                return PolicyDecision.DENY
        return PolicyDecision.ALLOW
