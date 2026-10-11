from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class PluginStatus(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    INITIALIZED = "initialized"
    AVAILABLE = "available"
    REGISTERED = "registered"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class PluginManifest(BaseModel):
    plugin_id: str
    name: str
    version: str
    api_version: str
    manifest_version: str = "1.0"
    entry_point: str
    description: str
    capabilities: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    license: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
