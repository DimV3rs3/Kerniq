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
    allowed_files: List[str] = field(default_factory=list)
    strict_attachments: bool = False
    cancelled: bool = False

    def add_message(self, message: Message):
        self.messages.append(message)
        try:
            dumped = message.model_dump(mode="json")
        except Exception:
            dumped = {"role": "assistant", "content": str(getattr(message, "content", ""))}
        self.metadata.setdefault("transcript", []).append(dumped)
