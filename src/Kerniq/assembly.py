"""Compose a tool registry from discovered packs. No hardcoded tool list."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .security.policy import SecurityPolicy
from .tools.loader import load_all_tools
from .tools.registry import ToolRegistry
from .tools.runtime_settings import apply_stored_tool_settings
from .tools.settings import ToolSettingsStore


def _tool_enabled(settings: Any, tool: Any) -> bool:
    enabled_map = getattr(settings, "enabled_tools", None) or {}
    if tool.tool_id in enabled_map:
        return bool(enabled_map[tool.tool_id])
    if tool.name in enabled_map:
        return bool(enabled_map[tool.name])
    if hasattr(settings, "is_tool_enabled"):
        return bool(settings.is_tool_enabled(tool.name))
    return True


def build_tool_registry(
    workspace: Path | str,
    *,
    config: Any,
    state_dir: Path | str,
    auto_approve_up_to: Optional[str] = None,
    host_freedom: bool = False,
) -> tuple[ToolRegistry, SecurityPolicy]:
    workspace_path = Path(workspace)
    security = config.security
    server_on = bool(getattr(getattr(config, "server", None), "enabled", False))
    policy = SecurityPolicy(
        workspace_root=workspace_path,
        disallowed_commands=list(security.disallowed_terminal_commands or []),
        require_approval_for_high_risk=bool(security.require_approval_for_high_risk),
        allow_terminal_network=bool(getattr(security, "allow_terminal_network", False)),
        auto_approve_up_to=auto_approve_up_to or getattr(security, "auto_approve_up_to", "low"),
        host_freedom=bool(host_freedom) and not server_on,
    )
    store = ToolSettingsStore(state_dir)
    ts = store.settings
    registry = ToolRegistry()
    tools = load_all_tools(str(workspace_path), policy=policy)
    apply_stored_tool_settings(tools, state_dir)
    for tool in tools:
        if not _tool_enabled(ts, tool):
            continue
        try:
            if tool.name == "web_search" and hasattr(tool, "apply_settings"):
                tool.apply_settings(
                    {
                        "max_results": getattr(ts, "web_search_max_results", 5),
                        "timeout": getattr(ts, "web_search_timeout", 15),
                    }
                )
            if tool.name == "fetch_url" and hasattr(tool, "apply_settings"):
                tool.apply_settings({"timeout": getattr(ts, "fetch_url_timeout", 20)})
        except Exception:
            pass
        try:
            registry.register_tool(tool)
        except ValueError:
            pass
    return registry, policy
