"""Anthropic Messages API (Claude). Tool use is native, not OpenAI-shaped."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

import httpx

from ...interfaces.errors import ErrorCode, ProviderError
from ...interfaces.models import (
    Message,
    MessageRole,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    ToolCall,
)
from ...interfaces.providers import ModelProvider
from ..cancel import StreamCancelled, await_unless_cancelled, cancelled_response

logger = logging.getLogger(__name__)

_API_VERSION = "2023-06-01"


class AnthropicProvider(ModelProvider):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.anthropic.com",
        timeout: float = 600.0,
    ):
        self.api_key = api_key or None
        self.model = (model or "").strip() or None
        self.base_url = (base_url or "https://api.anthropic.com").rstrip("/")
        self.timeout = timeout

    @property
    def provider_id(self) -> str:
        return "anthropic"

    def get_capabilities(self) -> Dict[str, Any]:
        return {"tool_calls": True, "streaming": False, "vision": False, "reasoning": False}

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": _API_VERSION,
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _client(self) -> httpx.AsyncClient:
        t = float(self.timeout or 600.0)
        return httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=t, write=60.0, pool=30.0),
            follow_redirects=True,
        )

    async def list_models(self) -> List[Dict[str, Any]]:
        if not self.api_key:
            raise ProviderError(ErrorCode.AUTHENTICATION_ERROR, "Claude API key is required")
        url = f"{self.base_url}/v1/models"
        try:
            async with self._client() as client:
                response = await client.get(url, headers=self._headers())
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Anthropic is unreachable: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(ErrorCode.AUTHENTICATION_ERROR, "Anthropic rejected the API key")
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"Anthropic models failed: {response.status_code} {response.text[:300]}",
            )
        data = response.json()
        rows = data.get("data") if isinstance(data, dict) else []
        result = []
        for item in rows or []:
            mid = str(item.get("id") or "")
            if mid:
                result.append({"id": mid, "name": item.get("display_name") or mid})
        return result

    async def check_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception as exc:
            logger.error("Anthropic connection check failed: %s", exc)
            return False

    def _convert(self, messages: List[Message]) -> tuple[str, List[Dict[str, Any]]]:
        system_parts: List[str] = []
        out: List[Dict[str, Any]] = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                if msg.content:
                    system_parts.append(msg.content)
                continue
            if msg.role == MessageRole.USER:
                out.append({"role": "user", "content": msg.content or ""})
            elif msg.role == MessageRole.ASSISTANT:
                blocks: List[Dict[str, Any]] = []
                if msg.content:
                    blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls or []:
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments or {},
                        }
                    )
                if not blocks:
                    blocks = [{"type": "text", "text": ""}]
                out.append({"role": "assistant", "content": blocks})
            elif msg.role == MessageRole.TOOL:
                block = {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content or "",
                }
                if (
                    out
                    and out[-1]["role"] == "user"
                    and isinstance(out[-1]["content"], list)
                    and out[-1]["content"]
                    and isinstance(out[-1]["content"][0], dict)
                    and out[-1]["content"][0].get("type") == "tool_result"
                ):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
        merged: List[Dict[str, Any]] = []
        for item in out:
            if merged and merged[-1]["role"] == item["role"] and isinstance(item["content"], str) and isinstance(merged[-1]["content"], str):
                merged[-1]["content"] = (merged[-1]["content"] + "\n\n" + item["content"]).strip()
            else:
                merged.append(item)
        return "\n\n".join(system_parts), merged

    def _tools(self, tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        out = []
        for tdef in tools or []:
            if not isinstance(tdef, dict):
                continue
            fn = tdef.get("function") if tdef.get("type") == "function" else tdef
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if not name:
                continue
            schema = fn.get("parameters") or fn.get("input_schema") or {"type": "object", "properties": {}}
            out.append(
                {
                    "name": name,
                    "description": fn.get("description") or "",
                    "input_schema": schema,
                }
            )
        return out

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise ProviderError(ErrorCode.AUTHENTICATION_ERROR, "Claude API key is required")
        model = self.model
        if not model:
            models = await self.list_models()
            if not models:
                raise ProviderError(ErrorCode.PROVIDER_REQUEST_FAILED, "Claude: no model available")
            model = str(models[0]["id"])
        system, messages = self._convert(request.messages)
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(request.options.max_tokens or 4096) if request.options else 4096,
            "messages": messages or [{"role": "user", "content": "Continue."}],
        }
        if system:
            payload["system"] = system
        if request.options and request.options.temperature is not None:
            payload["temperature"] = request.options.temperature
        tools = self._tools(request.tools)
        if tools:
            payload["tools"] = tools
        url = f"{self.base_url}/v1/messages"
        cancel_check = (request.metadata or {}).get("cancel_check")
        try:
            async with self._client() as client:
                try:
                    response = await await_unless_cancelled(
                        client.post(url, json=payload, headers=self._headers()),
                        cancel_check,
                    )
                except StreamCancelled:
                    return cancelled_response()
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Anthropic request failed: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(ErrorCode.AUTHENTICATION_ERROR, "Anthropic rejected the API key")
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"Anthropic chat error {response.status_code}: {response.text[:400]}",
            )
        data = response.json()
        texts: List[str] = []
        tool_calls: List[ToolCall] = []
        for block in data.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                raw_in = block.get("input") or {}
                tool_calls.append(
                    ToolCall(
                        id=str(block.get("id") or uuid.uuid4()),
                        name=str(block.get("name") or "unknown"),
                        arguments=raw_in if isinstance(raw_in, dict) else {"raw": raw_in},
                    )
                )
        usage_raw = data.get("usage") or {}
        usage = None
        if usage_raw:
            prompt = usage_raw.get("input_tokens")
            completion = usage_raw.get("output_tokens")
            total = None
            if prompt is not None or completion is not None:
                total = int(prompt or 0) + int(completion or 0)
            usage = TokenUsage(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
            )
        stop = data.get("stop_reason") or ("tool_use" if tool_calls else "end_turn")
        finish = "tool_calls" if tool_calls or stop == "tool_use" else "stop"
        return ModelResponse(
            messages=[
                Message(
                    role=MessageRole.ASSISTANT,
                    content="".join(texts),
                    tool_calls=tool_calls or None,
                )
            ],
            finish_reason=finish,
            usage=usage,
            request_id=data.get("id"),
            metadata={"api": "anthropic", "model": data.get("model") or model},
        )
