from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID

class ApprovalRequest(BaseModel):
    request_id: UUID
    tool_id: str
    arguments: Dict[str, Any]
    risk_level: str
    description: str
    timestamp: str

class ApprovalResult(BaseModel):
    decision: str # "allow", "deny"
    comment: Optional[str] = None
    user_id: Optional[str] = None

class ApprovalProvider(ABC):
    @abstractmethod\n    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        \"\"\"
        Requests approval for a tool execution. 
        This could be a CLI prompt, an HTTP call to a UI, etc.
        \"\"\"
        pass

class ConsoleApprovalProvider(ApprovalProvider):
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        print(f"\n--- APPROVAL REQUIRED ---")
        print(f"Tool: {request.tool_id}")
        print(f"Args: {request.arguments}")
        print(f"Risk: {request.risk_level}")
        print(f"Description: {request.description}")
        
        choice = input("Allow this operation? (y/n): ").lower()
        if choice == 'y':
            return ApprovalResult(decision=\"allow\")
        else:
            return ApprovalResult(decision=\"deny\", comment=\"User denied the request\")
