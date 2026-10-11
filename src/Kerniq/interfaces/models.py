from enum import Enum
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from uuid import UUID

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class Message(BaseModel):
    role: MessageRole
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class GenerationOptions(BaseModel):
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 1.0
    stop: Optional[List[str]] = None
    streaming: bool = False
    extra_params: Dict[str, Any] = Field(default_factory=dict)

class TokenUsage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

class ModelRequest(BaseModel):
    messages: List[Message]
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    tools: Optional[List[Dict[str, Any]]] = None
    session_id: UUID
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ModelResponse(BaseModel):
    messages: List[Message]
    finish_reason: str
    usage: Optional[TokenUsage] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
