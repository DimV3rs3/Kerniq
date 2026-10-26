"""In server mode a loaded model is not unloaded. Work waits for it."""

from __future__ import annotations

from typing import Any, Optional

UNLOAD_REFUSED = (
    "Server mode does not unload models. The task waits until the working model finishes."
)


def unload_allowed(server_mode: bool, choice: str) -> bool:
    if not server_mode:
        return True
    return str(choice or "") not in {"unload", "unload_busy"}


class RunQueue:
    """One worker. A second task is stored until the running one finishes."""

    def __init__(self) -> None:
        self._pending: list[Any] = []

    def admit(self, item: Any, *, busy: bool) -> dict[str, Any]:
        if busy or self._pending:
            self._pending.append(item)
            return {"queued": True, "position": len(self._pending)}
        return {"queued": False, "position": 0}

    def next(self) -> Optional[Any]:
        if not self._pending:
            return None
        return self._pending.pop(0)

    def drop(self, predicate) -> Optional[Any]:
        for index, item in enumerate(self._pending):
            if predicate(item):
                return self._pending.pop(index)
        return None

    def __len__(self) -> int:
        return len(self._pending)
