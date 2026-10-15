"""Human approval for high-risk tool calls."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel
from uuid import UUID


class ApprovalRequest(BaseModel):
    request_id: UUID
    tool_id: str
    arguments: Dict[str, Any]
    risk_level: str
    description: str
    timestamp: str
    consequences: str = ""


class ApprovalResult(BaseModel):
    decision: str  # "allow", "deny"
    comment: Optional[str] = None
    user_id: Optional[str] = None


class ApprovalProvider(ABC):
    @abstractmethod
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """Pause until a human allows or denies the action."""


class ConsoleApprovalProvider(ApprovalProvider):
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        print("\n--- APPROVAL REQUIRED ---")
        print(f"Tool: {request.tool_id}")
        print(f"Args: {request.arguments}")
        print(f"Risk: {request.risk_level}")
        print(f"Description: {request.description}")
        if request.consequences:
            print(f"Consequences: {request.consequences}")
        try:
            choice = input("Allow this operation? (y/n): ").strip().lower()
        except EOFError:
            return ApprovalResult(decision="deny", comment="No interactive approval (EOF)")
        if choice == "y":
            return ApprovalResult(decision="allow")
        return ApprovalResult(decision="deny", comment="User denied the request")
