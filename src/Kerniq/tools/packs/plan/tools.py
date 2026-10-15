"""update_plan — the only way the agent publishes the floating TODO list."""

from __future__ import annotations

from typing import Any, Dict, List

from ....interfaces.tools import Tool, ToolResult

_DONE = {"done", "complete", "completed", "x", "finished"}
_ACTIVE = {"active", "doing", "in_progress", "current", "progress", "wip"}


def normalize_status(value: Any) -> str:
    raw = str(value or "pending").strip().lower().replace(" ", "_")
    if raw in _DONE:
        return "done"
    if raw in _ACTIVE:
        return "active"
    return "pending"


def normalize_plan_items(raw_items: Any) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not isinstance(raw_items, list):
        return items
    seen = set()
    for index, raw in enumerate(raw_items):
        if isinstance(raw, str):
            title = raw.strip()
            item_id = f"step-{index + 1}"
            status = "pending"
        elif isinstance(raw, dict):
            title = str(raw.get("title") or raw.get("text") or "").strip()
            item_id = str(raw.get("id") or f"step-{index + 1}").strip() or f"step-{index + 1}"
            status = normalize_status(raw.get("status"))
        else:
            continue
        if not title or item_id in seen:
            continue
        seen.add(item_id)
        items.append({"id": item_id, "title": title, "status": status})
    return items


class UpdatePlanTool(Tool):
    @property
    def tool_id(self) -> str:
        return "update_plan"

    @property
    def name(self) -> str:
        return "update_plan"

    @property
    def description(self) -> str:
        return (
            "Replace the TODO. Each item has id, title, and status "
            "(pending, active, or done). Exactly one item should be active while working. "
            "Plan mode publishes the detailed breakdown and does not implement it. "
            "Act mode uses the same TODO to do the work and to close steps. "
            "Done items are kept in memory and hidden in the UI. Do not repeat them. "
            "The task cannot finish while any item is still pending or active."
        )

    @property
    def risk_level(self) -> str:
        return "read_only"

    @property
    def category(self) -> str:
        return "plan"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Full plan, in order. This replaces the previous plan.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "active", "done"],
                            },
                        },
                        "required": ["id", "title", "status"],
                    },
                }
            },
            "required": ["items"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        items = normalize_plan_items((arguments or {}).get("items"))
        archive: List[Dict[str, str]] = []
        if context is not None and getattr(context, "metadata", None) is not None:
            seen = set()
            for old in list(context.metadata.get("plan_archive") or []):
                if isinstance(old, dict) and old.get("id") and old["id"] not in seen:
                    archive.append(dict(old))
                    seen.add(old["id"])
            for old in list(context.metadata.get("plan") or []):
                if isinstance(old, dict) and old.get("status") == "done" and old.get("id") not in seen:
                    archive.append({"id": old["id"], "title": old.get("title") or "", "status": "done"})
                    seen.add(old["id"])
            for item in items:
                if item.get("status") == "done" and item.get("id") not in seen:
                    archive.append(dict(item))
                    seen.add(item["id"])
            context.metadata["plan"] = items
            context.metadata["plan_archive"] = archive
        open_items = [item for item in items if item.get("status") != "done"]
        return ToolResult(
            tool_call_id="",
            tool_id=self.tool_id,
            status="success",
            success=True,
            output={"items": items, "open": open_items, "archive": archive},
            human_readable=(
                f"TODO updated ({len(open_items)} open, {len(archive)} archived done). "
                "Archived items are memory only. Do not repeat them."
            ),
        )
