import asyncio
from typing import Dict, Any, List
from uuid import uuid4
from ...interfaces.providers import ModelProvider
from ...interfaces.models import ModelRequest, ModelResponse, Message, MessageRole, TokenUsage

class MockProvider(ModelProvider):
    def __init__(self, responses: List[Any] = None):
        self._responses = responses or []
        self._response_index = 0

    @property
    def provider_id(self) -> str:
        return "mock_provider"

    async def check_connection(self) -> bool:
        return True

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "tool_calls": True,
            "streaming": False,
            "vision": False,
            "reasoning": False
        }

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self._responses:
            # Default response if no specific responses are configured
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="I am a mock provider.")],
                finish_reason="stop",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20)
            )

        # Return the next configured response
        response = self._responses[self._response_index]
        self._response_index = (self._response_index + 1) % len(self._responses)
        
        if isinstance(response, ModelResponse):
            return response
        
        # If it's just a string, wrap it in a ModelResponse
        return ModelResponse(
            messages=[Message(role=MessageRole.ASSISTANT, content=str(response))],
            finish_reason="stop"
        )

    def set_responses(self, responses: List[Any]):
        self._responses = responses
        self._response_index = 0
