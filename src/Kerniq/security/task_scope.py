"""Per-task context visible to tools without threading it through every helper."""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Any, Iterator, Optional

_current: contextvars.ContextVar[Any] = contextvars.ContextVar("kerniq_task", default=None)


def current_task() -> Any:
    return _current.get()


@contextmanager
def use_task(task: Any) -> Iterator[None]:
    token = _current.set(task)
    try:
        yield
    finally:
        _current.reset(token)


def strict_allows(workspace_relative: str, task: Optional[Any]) -> Optional[str]:
    """Return an error string when strict attachment mode blocks this path."""
    if task is None or not getattr(task, "strict_attachments", False):
        return None
    allowed = getattr(task, "allowed_files", None) or []
    rel = workspace_relative.replace("\\", "/").lstrip("./")
    normalized = []
    for item in allowed:
        text = str(item).replace("\\", "/").lstrip("./")
        if text:
            normalized.append(text)
    if rel in normalized:
        return None
    for item in normalized:
        prefix = item.rstrip("/") + "/"
        if rel.startswith(prefix):
            return None
    return (
        f"Strict attachment mode: '{rel}' is not in the allowed file list "
        f"({', '.join(normalized) or 'empty'})"
    )
