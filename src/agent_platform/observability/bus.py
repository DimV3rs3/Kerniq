import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from uuid import UUID

class EventSink:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def emit(self, event_type: str, component: str, data: Dict[str, Any], 
                  level: str = "INFO", session_id: Optional[UUID] = None, 
                  task_id: Optional[UUID] = None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "component": component,
            "level": level,
            "session_id": str(session_id) if session_id else None,
            "task_id": str(task_id) if task_id else None,
            "data": data
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

class EventBus:
    def __init__(self, sink: Optional[EventSink] = None):
        self.sink = sink

    async def publish(self, event_type: str, component: str, data: Dict[str, Any], 
                      level: str = "INFO", session_id: Optional[UUID] = None, 
                      task_id: Optional[UUID] = None):
        if self.sink:
            await self.sink.emit(event_type, component, data, level, session_id, task_id)
