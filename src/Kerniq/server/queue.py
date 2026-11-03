"""In server mode a loaded model is not unloaded. Work waits for it."""

from __future__ import annotations

from typing import Any, Optional

UNLOAD_REFUSED = (
    "Server mode does not unload models. The task waits until the working model finishes."
)

LOCAL_PROVIDER_REFUSED = (
    "Server mode does not connect to local model providers. "
    "Choose a cloud provider, or ask the administrator to turn debug mode on."
)


def unload_allowed(server_mode: bool, choice: str) -> bool:
    if not server_mode:
        return True
    return str(choice or "") not in {"unload", "unload_busy"}


def same_user_waiting(runs: dict, pending: list, user_id: str) -> bool:
    """True when this user already has a live run or something queued ahead of them.

    Other users are ignored. Server mode runs those at the same time.
    """
    user_id = str(user_id or "")
    for run in (runs or {}).values():
        if not isinstance(run, dict):
            continue
        if run.get("done") or run.get("queued"):
            continue
        if str(run.get("user_id") or "") == user_id:
            return True
    for item in pending or []:
        payload = item[2] if isinstance(item, tuple) and len(item) > 2 else {}
        if str((payload or {}).get("user_id") or "") == user_id:
            return True
    return False


class RateWindow:
    """How many events one key may start in a rolling minute. Zero means no limit."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int, now: float) -> bool:
        try:
            cap = int(limit)
        except (TypeError, ValueError):
            cap = 0
        if cap <= 0:
            return True
        name = str(key or "")
        hits = [stamp for stamp in self._hits.get(name, []) if now - stamp < 60]
        if len(hits) >= cap:
            self._hits[name] = hits
            return False
        hits.append(now)
        self._hits[name] = hits
        return True


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
