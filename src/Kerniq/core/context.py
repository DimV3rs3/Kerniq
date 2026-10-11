from dataclasses import dataclass, field
from typing import List, Optional
from uuid import UUID
from ..interfaces.models import Message

@dataclass
class TaskContext:
    task_id: UUID
    session_id: UUID
    goal: str
    messages: List[Message] = field(default_factory=list)
    workspace: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def add_message(self, message: Message):
        self.messages.append(message)
