"""update_plan — the only way the agent publishes the floating TODO list."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from ....interfaces.tools import Tool, ToolResult

_DONE = {"done", "complete", "completed", "x", "finished"}
_ACTIVE = {"active", "doing", "in_progress", "current", "progress", "wip"}
_SKIP = {"skipped", "skip", "cancelled", "canceled", "wont_do"}
_FROZEN = {"frozen", "freeze", "paused", "pause", "hold", "on_hold"}
_FAILED = {"failed", "fail", "failure"}

# Closed items do not block the end of the task. Frozen and failed do.
CLOSED_PLAN_STATUSES = frozenset({"done", "skipped"})


def normalize_status(value: Any) -> str:
    raw = str(value or "pending").strip().lower().replace(" ", "_")
    if raw in _DONE:
        return "done"
    if raw in _SKIP:
        return "skipped"
    if raw in _FROZEN:
        return "frozen"
    if raw in _FAILED:
        return "failed"
    if raw in _ACTIVE:
        return "active"
    return "pending"


def is_open_status(value: Any) -> bool:
    return normalize_status(value) not in CLOSED_PLAN_STATUSES


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


def _first_open_index(items: List[Dict[str, str]]) -> int | None:
    for index, item in enumerate(items):
        if item["status"] not in CLOSED_PLAN_STATUSES:
            return index
    return None


def _single_active(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """One item in progress: the first that is not done or skipped.

    Later items stay pending until that one is done. A frozen or failed cursor
    stays as it is, and nothing after it may be active, done, frozen, or failed.
    """
    cursor = _first_open_index(items)
    if cursor is None:
        for item in items:
            if item["status"] == "active":
                item["status"] = "done"
        return items
    for index, item in enumerate(items):
        if index < cursor:
            if item["status"] == "active":
                item["status"] = "done"
            continue
        if index == cursor:
            if item["status"] in ("pending", "active"):
                item["status"] = "active"
            continue
        if item["status"] != "pending":
            item["status"] = "pending"
    return items


def _numeric_id(item_id: str):
    text = str(item_id or "").strip()
    if text.isdigit():
        return int(text)
    match = re.fullmatch(r"(?:step|item|todo)[-_ ]?(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _order_numeric(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """If every id is numeric, show 1,2,3 rather than the order the model typed."""
    ranks = [_numeric_id(item["id"]) for item in items]
    if not ranks or any(rank is None for rank in ranks):
        return items
    paired = sorted(enumerate(items), key=lambda pair: (ranks[pair[0]], pair[0]))
    return [item for _index, item in paired]


def merge_plan(previous: Any, incoming: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Keep every existing item. New items may be inserted only from the current one down.

    If 1–3 are done, 4 is active, and 5–7 follow, a new id may land between 4, 5, 6, 7
    or after 7. An attempt to insert it among the finished prefix is clamped to just
    after the active item. Existing titles are not rewritten. Nothing is deleted.
    Only the current item may change status, and only that one per call.
    The list is then forced back to a single in-progress item, in order.
    """
    prior = normalize_plan_items(previous)
    fresh = normalize_plan_items(incoming)
    if not prior:
        return _single_active(_order_numeric(fresh))
    by_id = {item["id"]: dict(item) for item in prior}
    for item in fresh:
        current = by_id.get(item["id"])
        if current is None:
            by_id[item["id"]] = dict(item)
            continue
        current["status"] = item["status"]

    active_at = next((i for i, item in enumerate(prior) if item["status"] == "active"), None)
    if active_at is None:
        min_pos = next(
            (i for i, item in enumerate(prior) if item["status"] not in CLOSED_PLAN_STATUSES),
            len(prior),
        )
    else:
        min_pos = active_at + 1

    order = [item["id"] for item in prior]
    known = set(order)
    incoming_ids = [item["id"] for item in fresh]
    for item in fresh:
        item_id = item["id"]
        if item_id in known:
            continue
        rank = _numeric_id(item_id)
        order_ranks = [_numeric_id(existing) for existing in order]
        if rank is not None and order_ranks and all(item is not None for item in order_ranks):
            pos = sum(1 for existing in order_ranks if existing < rank)
        else:
            try:
                at = incoming_ids.index(item_id)
            except ValueError:
                at = len(incoming_ids)
            anchor = next((later for later in incoming_ids[at + 1 :] if later in known), None)
            pos = order.index(anchor) if anchor is not None else len(order)
        if pos < min_pos:
            pos = min_pos
        order.insert(pos, item_id)
        known.add(item_id)
    merged = [by_id[item_id] for item_id in order]
    prior_status = {item["id"]: item["status"] for item in prior}
    cursor = _first_open_index(prior)
    cursor_id = prior[cursor]["id"] if cursor is not None else None
    for item in merged:
        old = prior_status.get(item["id"])
        if old is None or item["id"] == cursor_id:
            continue
        item["status"] = old
    return _single_active(merged)


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
            "Publish the TODO. Send the full list in order. You cannot delete an item or rename an existing one. "
            "Work strictly in order, one item at a time. Exactly one item is in progress: the first item that is not done. "
            "Each call may change the status of that current item only. "
            "If you cannot finish it, mark that one item failed. Do not start, finish, freeze, or fail a later item in the same call. "
            "The next item becomes current only after the current one is done. "
            "New items may be inserted only among the current item and the items after it. "
            "status is pending, active, done, frozen, or failed. "
            "done stays on the list. frozen pauses the current item. failed marks it failed. Both still block the end. "
            "An empty list does not clear the TODO."
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
                    "description": (
                        "Full ordered TODO. Existing ids are kept even if omitted. "
                        "New ids are inserted only from the current item downward."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "active", "done", "frozen", "failed", "skipped"],
                            },
                        },
                        "required": ["id", "title", "status"],
                    },
                }
            },
            "required": ["items"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        incoming = normalize_plan_items((arguments or {}).get("items"))
        previous = []
        if context is not None and getattr(context, "metadata", None) is not None:
            previous = list(context.metadata.get("plan") or [])
        items = merge_plan(previous, incoming)
        archive: List[Dict[str, str]] = []
        if context is not None and getattr(context, "metadata", None) is not None:
            seen = set()
            for old in list(context.metadata.get("plan_archive") or []):
                if isinstance(old, dict) and old.get("id") and old["id"] not in seen:
                    archive.append(dict(old))
                    seen.add(old["id"])
            for old in list(context.metadata.get("plan") or []):
                if (
                    isinstance(old, dict)
                    and old.get("status") in CLOSED_PLAN_STATUSES
                    and old.get("id") not in seen
                ):
                    archive.append({"id": old["id"], "title": old.get("title") or "", "status": old.get("status")})
                    seen.add(old["id"])
            for item in items:
                if item.get("status") in CLOSED_PLAN_STATUSES and item.get("id") not in seen:
                    archive.append(dict(item))
                    seen.add(item["id"])
            context.metadata["plan"] = items
            context.metadata["plan_archive"] = archive
        open_items = [item for item in items if is_open_status(item.get("status"))]
        frozen = [item for item in open_items if item.get("status") == "frozen"]
        return ToolResult(
            tool_call_id="",
            tool_id=self.tool_id,
            status="success",
            success=True,
            output={"items": items, "open": open_items, "archive": archive},
            human_readable=(
                f"TODO updated ({len(open_items)} open, {len(frozen)} frozen, {len(archive)} archived). "
                "Nothing was deleted. Only the current item can change, and only one item per call. "
                "Later items stay pending until the current one is done. "
                "If you cannot finish the current item, mark that one failed and keep working or retry it. "
                "Completed items stay on the list."
            ),
        )
