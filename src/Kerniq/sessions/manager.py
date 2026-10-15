"""Durable task sessions. Corrupt files are skipped, never raised."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from ..interfaces.storage import StorageValue
from ..storage.json_store import JsonStorage


def _dump_message(message: Any) -> Any:
    if hasattr(message, "model_dump"):
        return message.model_dump(mode="json")
    if isinstance(message, dict):
        return message
    return {"role": "assistant", "content": str(message)}


class SessionManager:
    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _key(self, session_id: Any) -> str:
        return f"session-{session_id}"

    def _payload(
        self,
        *,
        session_id: Any,
        task_id: Any,
        goal: str,
        status: str,
        result: str,
        workspace: str,
        messages: Optional[Iterable[Any]] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "session_id": str(session_id),
            "task_id": str(task_id),
            "goal": goal,
            "status": status,
            "result": result,
            "workspace": workspace,
            "messages": [_dump_message(m) for m in (messages or [])],
            "metadata": dict(metadata or {}),
        }

    async def save_task(
        self,
        *,
        session_id: Any,
        task_id: Any,
        goal: str,
        status: str,
        result: str,
        workspace: str,
        messages: Optional[Iterable[Any]] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        payload = self._payload(
            session_id=session_id,
            task_id=task_id,
            goal=goal,
            status=status,
            result=result,
            workspace=workspace,
            messages=messages,
            metadata=metadata,
        )
        await self.storage.put(self._key(session_id), StorageValue(data=payload))

    def save_task_sync(self, **kwargs: Any) -> None:
        """Write from a sync checkpoint inside the agent loop."""
        payload = self._payload(**kwargs)
        path = self.storage._get_path(self._key(kwargs["session_id"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            StorageValue(data=payload).model_dump_json(),
            encoding="utf-8",
        )

    async def get_session(self, session_id: Any) -> Optional[dict]:
        value = await self.storage.get(self._key(session_id))
        if value is None or not isinstance(value.data, dict):
            return None
        return value.data

    async def list_sessions(self) -> list[dict]:
        keys = await self.storage.list_keys("session-")
        rows = []
        for key in keys:
            value = await self.storage.get(key)
            if value is None or not isinstance(value.data, dict):
                continue
            data = value.data
            rows.append(
                {
                    "session_id": data.get("session_id") or key.removeprefix("session-"),
                    "goal": data.get("goal"),
                    "status": data.get("status"),
                    "task_id": data.get("task_id"),
                }
            )
        return rows
