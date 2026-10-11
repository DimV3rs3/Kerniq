import asyncio
import logging
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID

logger = logging.getLogger(__name__)

class Event(BaseModel):
    event_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    session_id: Optional[UUID] = None
    task_id: Optional[UUID] = None
    component: str
    event_type: str
    level: str = "INFO"
    data: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None

class EventSink(BaseModel):
    sink_id: str
    handler: Callable[[Event], Any]

class EventBus:
    def __init__(self, log_file: Optional[str] = None):
        self._subscribers: List[Callable[[Event], Any]] = []
        self._log_file = log_file
        self._lock = asyncio.Lock()

    def subscribe(self, callback: Callable[[Event], Any]):
        self._subscribers.append(callback)

    async def publish(self, event: Event):
        # Log to file if configured (JSONL)
        if self._log_file:
            await self._write_to_log(event)

        # Notify subscribers
        tasks = []
        for subscriber in self._subscribers:
            if asyncio.iscoroutinefunction(subscriber):
                tasks.append(subscriber(event))
            else:
                try:
                    subscriber(event)
                except Exception as e:
                    logger.error(f"Error in synchronous event subscriber: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _write_to_log(self, event: Event):
        async with self._lock:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(event.model_dump_json() + "\n")
            except Exception as e:
                logger.error(f"Failed to write event to log file: {e}")

    def create_event(self, component: str, event_type: str, data: Dict[str, Any], 
                     session_id: Optional[UUID] = None, task_id: Optional[UUID] = None, 
                     level: str = "INFO", correlation_id: Optional[str] = None) -> Event:
        import uuid
        return Event(
            event_id=str(uuid.uuid4()),
            component=component,
            event_type=event_type,
            data=data,
            session_id=session_id,
            task_id=task_id,
            level=level,
            correlation_id=correlation_id
        )
