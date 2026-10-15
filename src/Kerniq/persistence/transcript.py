"""Project a tool/thought stream into the chat the UI shows.

Only the latest thinking block is kept. Consecutive collapsible tool calls
then sit next to each other and can merge. This module is UI-agnostic so a
refresh rebuilds the same transcript the page was drawing.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


_THINK = {"think_collapsed", "think_live"}


def retain_latest_thought(messages: list[dict]) -> list[dict]:
    last = -1
    for i, msg in enumerate(messages):
        if msg.get("kind") in _THINK:
            last = i
    if last < 0:
        return list(messages)
    return [
        msg
        for i, msg in enumerate(messages)
        if msg.get("kind") not in _THINK or i == last
    ]


def aggregate_tools(
    messages: Iterable[dict],
    *,
    aggregate: bool = True,
    collapsible: Optional[set[str]] = None,
) -> list[dict]:
    """Merge consecutive calls of the same collapsible tool."""
    collapsible = collapsible or set()
    out: list[dict] = []
    for msg in messages:
        if (
            aggregate
            and msg.get("kind") == "tool"
            and msg.get("name") in collapsible
            and msg.get("status") != "pending"
        ):
            prev = out[-1] if out else None
            if prev and prev.get("kind") == "tool_agg" and prev.get("name") == msg.get("name"):
                prev["count"] = int(prev.get("count") or 1) + 1
                if msg.get("status") == "error" or msg.get("success") is False:
                    prev["errors"] = int(prev.get("errors") or 0) + 1
                continue
            out.append(
                {
                    "kind": "tool_agg",
                    "name": msg.get("name"),
                    "count": 1,
                    "errors": 1 if (msg.get("status") == "error" or msg.get("success") is False) else 0,
                }
            )
            continue
        out.append(msg)
    return out


def fold_transcript(
    messages: Iterable[dict],
    *,
    aggregate: bool = True,
    collapsible: Optional[set[str]] = None,
) -> list[dict]:
    kept = retain_latest_thought([dict(m) for m in messages])
    return aggregate_tools(kept, aggregate=aggregate, collapsible=collapsible)


def project_events(
    user_text: str,
    events: Iterable[dict],
    *,
    done: bool = False,
    attachments: Optional[list] = None,
) -> list[dict]:
    """Rebuild chat messages from the durable event log."""
    messages: list[dict] = [
        {
            "role": "user",
            "content": user_text or "",
            "attachments": list(attachments or []),
        }
    ]
    think_parts: list[str] = []
    live = ""
    finalized = False

    def _flush_think() -> None:
        nonlocal think_parts
        text = "".join(think_parts).strip()
        think_parts = []
        if text:
            messages.append({"kind": "think_collapsed", "text": text})

    for event in events:
        kind = event.get("type")
        if kind == "reasoning_delta":
            think_parts.append(event.get("text") or "")
        elif kind == "think_done":
            text = (event.get("text") or "").strip()
            if text:
                think_parts = [text]
            _flush_think()
        elif kind == "content_delta":
            live += event.get("text") or ""
        elif kind == "tool":
            if live.strip():
                messages.append({"kind": "think_collapsed", "text": live.strip()})
                live = ""
            _flush_think()
            if event.get("status") == "pending":
                continue
            messages.append(
                {
                    "kind": "tool",
                    "name": event.get("name"),
                    "status": event.get("status"),
                    "success": event.get("success", event.get("status") != "error"),
                    "stop_reason": event.get("stop_reason"),
                    "summary": event.get("summary") or "",
                    "args": event.get("args"),
                }
            )
        elif kind == "file_op":
            messages.append(
                {
                    "kind": "file_op",
                    "op": event.get("op"),
                    "path": event.get("path"),
                    "added": event.get("added"),
                    "removed": event.get("removed"),
                }
            )
        elif kind == "assistant":
            content = (event.get("content") or live or "").replace("TASK_COMPLETED", "").strip()
            live = ""
            think_parts = []
            finalized = True
            if content:
                messages.append(
                    {
                        "role": "assistant",
                        "content": content,
                        "completed": bool(event.get("completed")),
                    }
                )
        elif kind == "status" and event.get("status") in ("cancelled", "error"):
            text = (event.get("text") or "").strip()
            if text:
                messages.append({"role": "system", "content": text, "kind": "status"})
    if not finalized:
        if think_parts:
            text = "".join(think_parts).strip()
            if text:
                messages.append(
                    {
                        "kind": "think_live" if not done else "think_collapsed",
                        "text": text,
                    }
                )
        if live.strip():
            messages.append(
                {"kind": "assistant_live", "role": "assistant", "content": live}
            )
    return retain_latest_thought(messages)
