from typing import Protocol, Any, Optional, List
from dataclasses import dataclass
from uuid import UUID
from .models import ModelResponse, ModelRequest

@dataclass
class TaskResult:
    status: str  # SUCCESS, FAILED, CANCELLED, LIMIT_REACHED, etc.
    final_answer: str
    session_id: UUID
    metrics: dict[str, Any]

class Agent(Protocol):
    async def run(self, task: str, workspace: str, **kwargs) -> TaskResult:
        ...
