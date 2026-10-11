from abc import ABC, abstractmethod
from typing import Any, Optional, List
from pydantic import BaseModel
from uuid import UUID

class StorageValue(BaseModel):
    data: Any
    metadata: dict[str, Any] = {}

class Storage(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[StorageValue]:
        pass

    @abstractmethod
    async def put(self, key: str, value: StorageValue) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

    @abstractmethod
    async def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
