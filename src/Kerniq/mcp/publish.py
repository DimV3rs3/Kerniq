"""Decide which tools an MCP server advertises.

An empty allowlist is not a snapshot of today's tools. It means: publish every
currently registered tool the policy would run without a human. New packs show
up on the next process start. An explicit list is still honored.
Critical tools are never auto-published; MCP has no approval dialog.
update_plan is never published: it is the Kerniq TODO, not a standalone tool.
Plugin manager commands are not agent tools and are not published.
"""

from __future__ import annotations

from typing import Any, Sequence

from ..security.policy import PolicyDecision, RiskLevel


_NEVER_PUBLISH = frozenset({"update_plan"})


def resolve_published_names(
    registry: Any,
    policy: Any,
    configured: Sequence[str] | None,
) -> list[str]:
    explicit = [str(name).strip() for name in (configured or []) if str(name).strip()]
    if explicit and explicit != ["*"]:
        # update_plan stays tied to the Kerniq TODO UI. MCP clients must not receive it.
        return [name for name in explicit if name not in _NEVER_PUBLISH and not name.startswith("plugin_")]
    publish_all = explicit == ["*"]
    names: list[str] = []
    for tool in registry.list_tools():
        if getattr(tool, "agent_visible", True) is False:
            continue
        if tool.name in _NEVER_PUBLISH or str(tool.name).startswith("plugin_"):
            continue
        risk = policy.resolve_risk(tool.name, getattr(tool, "risk_level", None), tool)
        if risk == RiskLevel.CRITICAL:
            continue
        if not publish_all:
            decision = policy.evaluate_tool_call(
                tool.name, {}, getattr(tool, "risk_level", None), tool=tool
            )
            if decision != PolicyDecision.ALLOW:
                continue
        names.append(tool.name)
    return names
