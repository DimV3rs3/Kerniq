from typing import List, Optional, Dict, Any
from .registry import ToolRegistry
from ..interfaces.providers import ModelProvider
from ..interfaces.models import ModelDescriptor

class ModelRouter:
    def __init__(self, providers: List[ModelProvider]):
        self.providers = providers

    def select_provider(self, required_capabilities: Optional[List[str]] = None, 
                        preferred_provider_id: Optional[str] = None) -> ModelProvider:
        # 1. Try preferred provider
        if preferred_provider_id:
            for p in self.providers:
                if p.provider_id == preferred_provider_id:
                    return p

        # 2. Try to find a provider with all required capabilities
        if required_capabilities:
            for p in self.providers:
                caps = p.get_capabilities()
                if all(caps.get(cap, False) for cap in required_capabilities):
                    return p

        # 3. Fallback to the first available provider
        if self.providers:
            return self.providers[0]
        
        raise RuntimeError("No suitable model provider found")
