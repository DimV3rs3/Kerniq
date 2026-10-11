from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from uuid import UUID

class MCPTool(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]

class MCPResource(BaseModel):
    uri: str
    name: str
    description: str
    mime_type: Optional[str] = None

class MCPPrompt(BaseModel):
    name: str
    description: str
    arguments: List[Dict[str, Any]] = Field(default_factory=list)
