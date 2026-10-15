"""Thread-safe approval queue for the Web UI (agent loop != HTTP thread)."""

from __future__ import annotations

import asyncio
import threading
from typing import Callable, Optional

from ..interfaces.approvals import ApprovalProvider, ApprovalRequest, ApprovalResult


class ApprovalBroker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: dict[str, dict] = {}

    def register(self, request: ApprovalRequest) -> None:
        rid = str(request.request_id)
        with self._lock:
            self._pending[rid] = {
                "event": threading.Event(),
                "decision": None,
                "comment": None,
                "request": request.model_dump(mode="json"),
            }

    def wait(self, request_id: str, timeout: float) -> Optional[tuple[str, Optional[str]]]:
        with self._lock:
            slot = self._pending.get(request_id)
        if slot is None:
            return ("deny", "unknown approval request")
        if not slot["event"].wait(timeout):
            return None
        with self._lock:
            self._pending.pop(request_id, None)
            return (slot["decision"] or "deny", slot["comment"])

    def decide(self, request_id: str, decision: str, comment: Optional[str] = None) -> dict:
        choice = (decision or "").strip().lower()
        if choice not in ("allow", "deny"):
            return {"ok": False, "error": "decision must be allow or deny"}
        with self._lock:
            slot = self._pending.get(str(request_id))
            if slot is None:
                return {"ok": False, "error": "no pending approval"}
            slot["decision"] = choice
            slot["comment"] = comment
            slot["event"].set()
        return {"ok": True, "request_id": str(request_id), "decision": choice}

    def list_pending(self) -> list:
        with self._lock:
            return [
                dict(slot["request"])
                for slot in self._pending.values()
                if isinstance(slot.get("request"), dict)
            ]


class BrokerApprovalProvider(ApprovalProvider):
    def __init__(
        self,
        broker: ApprovalBroker,
        on_pending: Callable[[ApprovalRequest], None],
        cancel_check: Optional[Callable[[], bool]] = None,
        timeout_seconds: float = 600.0,
    ) -> None:
        self.broker = broker
        self.on_pending = on_pending
        self.cancel_check = cancel_check
        self.timeout_seconds = timeout_seconds

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        rid = str(request.request_id)
        self.broker.register(request)
        try:
            self.on_pending(request)
        except Exception:
            self.broker.decide(rid, "deny", "failed to notify UI")
            return ApprovalResult(decision="deny", comment="failed to notify UI")
        loop = asyncio.get_running_loop()
        waited = 0.0
        while waited < self.timeout_seconds:
            if self.cancel_check and self.cancel_check():
                self.broker.decide(rid, "deny", "cancelled")
                return ApprovalResult(decision="deny", comment="cancelled")
            step = 0.4
            found = await loop.run_in_executor(None, self.broker.wait, rid, step)
            if found is not None:
                decision, comment = found
                return ApprovalResult(decision=decision, comment=comment)
            waited += step
        self.broker.decide(rid, "deny", "approval timed out")
        return ApprovalResult(decision="deny", comment="approval timed out")
