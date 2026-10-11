from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from .models import ModelRequest, ModelResponse

class ModelProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @abstractmethod
    async def check_connection(self) -> bool:
        pass

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        pass
