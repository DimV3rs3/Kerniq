"""Security policy engine for tool execution and workspace access."""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..interfaces.errors import SecurityError, ErrorCode
from .command_guard import assess_command, blacklist_hit


class RiskLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_RANK = {
    RiskLevel.READ_ONLY: 0,
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

# Trusted floor. A caller-supplied risk can raise this, never lower it.
_INTRINSIC_RISK = {
    "run_command": RiskLevel.CRITICAL,
    "terminal": RiskLevel.CRITICAL,
    "delete_file": RiskLevel.HIGH,
    "fs_delete_file": RiskLevel.HIGH,
    "write_file": RiskLevel.MEDIUM,
    "fs_write_file": RiskLevel.MEDIUM,
    "create_file": RiskLevel.MEDIUM,
    "edit_file": RiskLevel.MEDIUM,
    "move_file": RiskLevel.MEDIUM,
    "fs_move_file": RiskLevel.MEDIUM,
    "unzip": RiskLevel.MEDIUM,
    "create_directory": RiskLevel.MEDIUM,
}


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


def _parse_risk(value: RiskLevel | str | None) -> Optional[RiskLevel]:
    if value is None:
        return None
    if isinstance(value, RiskLevel):
        return value
    try:
        return RiskLevel(str(value))
    except ValueError:
        return RiskLevel.MEDIUM


class SecurityPolicy:
    def __init__(
        self,
        workspace_root: Path,
        disallowed_commands: Optional[List[str]] = None,
        require_approval_for_high_risk: bool = True,
        allow_terminal_network: bool = False,
        auto_approve_up_to: RiskLevel | str = RiskLevel.LOW,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.disallowed_commands = list(disallowed_commands or [])
        self.require_approval_for_high_risk = require_approval_for_high_risk
        self.allow_terminal_network = allow_terminal_network
        parsed = _parse_risk(auto_approve_up_to) or RiskLevel.LOW
        raw = str(auto_approve_up_to or "").strip().lower()
        self.bypass_all = raw in ("all", "bypass")
        if parsed == RiskLevel.CRITICAL and not self.bypass_all:
            parsed = RiskLevel.HIGH
        self.auto_approve_up_to = parsed

    def validate_path(self, path: str) -> Path:
        raw = str(path)
        if "\x00" in raw or raw.startswith("\\\\") or raw.startswith("//"):
            raise SecurityError(
                ErrorCode.PERMISSION_DENIED,
                f"Path {path} is outside the workspace root {self.workspace_root}",
            )
        try:
            p = Path(raw)
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

    def resolve_risk(
        self,
        tool_id: str,
        risk_level: RiskLevel | str | None = None,
        tool: Any = None,
    ) -> RiskLevel:
        """Highest of caller hint, tool declaration, and the intrinsic floor.

        Caller hints are untrusted. They cannot downgrade a tool below its floor.
        """
        candidates: List[RiskLevel] = []
        parsed = _parse_risk(risk_level)
        if parsed is not None:
            candidates.append(parsed)
        if tool is not None:
            declared = _parse_risk(getattr(tool, "risk_level", None))
            if declared is not None:
                candidates.append(declared)
        intrinsic = _INTRINSIC_RISK.get(tool_id)
        if intrinsic is None and tool is not None:
            intrinsic = _INTRINSIC_RISK.get(getattr(tool, "name", "")) or _INTRINSIC_RISK.get(
                getattr(tool, "tool_id", "")
            )
        if intrinsic is not None:
            candidates.append(intrinsic)
        if not candidates:
            return RiskLevel.MEDIUM
        return max(candidates, key=lambda item: _RISK_RANK[item])

    def terminal_block_reason(self, command: str) -> Optional[str]:
        verdict = assess_command(command, allow_network=self.allow_terminal_network)
        if not verdict.allowed:
            return verdict.reason
        hit = blacklist_hit(command, self.disallowed_commands)
        if hit:
            return f"Command matches disallowed pattern: {hit}"
        return None

    def evaluate_tool_call(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        risk_level: RiskLevel | str = RiskLevel.MEDIUM,
        tool: Any = None,
    ) -> PolicyDecision:
        arguments = arguments or {}
        if tool_id in ("run_command", "terminal") or (
            tool is not None and getattr(tool, "name", None) in ("run_command", "terminal")
        ):
            reason = self.terminal_block_reason(str(arguments.get("command", "")))
            if reason:
                return PolicyDecision.DENY

        name = getattr(tool, "name", None) or tool_id
        if name in ("write_file", "edit_file", "delete_file", "create_file", "move_file", "create_directory", "unzip"):
            from .task_scope import current_task
            task = current_task()
            external = []
            if task is not None:
                for item in ((getattr(task, "metadata", None) or {}).get("external_files") or []):
                    try:
                        external.append(str(Path(item).resolve()))
                    except Exception:
                        continue
            raw_paths = []
            for key in ("path", "destination", "src", "dst", "source"):
                raw = arguments.get(key)
                if raw:
                    raw_paths.append(str(raw))
            if raw_paths and external and not self.bypass_all:
                for raw_path in raw_paths:
                    try:
                        resolved = str(Path(raw_path).resolve())
                    except Exception:
                        resolved = raw_path
                    if resolved in external:
                        return PolicyDecision.REQUIRE_APPROVAL

        risk = self.resolve_risk(tool_id, risk_level, tool)
        if self.bypass_all:
            return PolicyDecision.ALLOW
        if risk == RiskLevel.CRITICAL:
            return PolicyDecision.REQUIRE_APPROVAL
        if tool is not None and bool(getattr(tool, "cfg_auto_accept", False)):
            return PolicyDecision.ALLOW
        ceiling = self.auto_approve_up_to
        if not self.require_approval_for_high_risk:
            ceiling = RiskLevel.HIGH
        if _RISK_RANK[risk] <= _RISK_RANK[ceiling]:
            return PolicyDecision.ALLOW
        return PolicyDecision.REQUIRE_APPROVAL

    def check_terminal_command(self, command: str) -> PolicyDecision:
        if self.terminal_block_reason(command):
            return PolicyDecision.DENY
        return PolicyDecision.ALLOW
