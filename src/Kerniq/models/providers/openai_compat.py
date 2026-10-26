"""OpenAI-compatible chat provider (DeepSeek, OpenRouter, OpenAI, Gemini, Groq, Mistral, Ollama)."""

from __future__ import annotations

import json
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
from ..cancel import StreamCancelled, await_unless_cancelled, cancelled_response, next_stream_line

logger = logging.getLogger(__name__)


def to_openai_messages(messages: List[Message]) -> List[Dict[str, Any]]:
    """One system message, and it is first.

    Qwen and other Jinja chat templates reject a second system role
    ("System message must be at the beginning"), so the identity prompt,
    the pinned TODO, and any compaction note are joined into that single
    leading message.

    Pictures travel as image parts. A tool that loaded one is followed by
    those parts only after every tool result for that turn is already in
    the list, so the model sees the picture and not a byte dump.
    """
    from Kerniq.models.vision import openai_image_parts

    system_parts: List[str] = []
    rest: List[Dict[str, Any]] = []
    pending_images: List[Dict[str, Any]] = []

    def flush_images() -> None:
        if not pending_images:
            return
        rest.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "The picture you asked to see is attached here. "
                        "Look at the image itself. It is not a list of bytes."
                    ),
                },
                *pending_images,
            ],
        })
        pending_images.clear()

    def user_content(msg: Message) -> Any:
        text = msg.content or ""
        images = openai_image_parts(getattr(msg, "metadata", None))
        if not images:
            return text
        parts: List[Dict[str, Any]] = []
        if text.strip():
            parts.append({"type": "text", "text": text})
        parts.extend(images)
        return parts

    for msg in messages:
        if msg.role != MessageRole.TOOL:
            flush_images()
        if msg.role == MessageRole.SYSTEM:
            text = (msg.content or "").strip()
            if text:
                system_parts.append(text)
            continue
        if msg.role == MessageRole.USER:
            rest.append({"role": "user", "content": user_content(msg)})
        elif msg.role == MessageRole.ASSISTANT:
            item: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments or {}, ensure_ascii=False),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            rest.append(item)
        elif msg.role == MessageRole.TOOL:
            rest.append(
                {
                    "role": "tool",
                    "tool_call_id": msg.tool_call_id or "",
                    "name": msg.name or "tool",
                    "content": msg.content or "",
                }
            )
            pending_images.extend(openai_image_parts(getattr(msg, "metadata", None)))
    flush_images()
    if not system_parts:
        return rest
    return [{"role": "system", "content": "\n\n".join(system_parts)}] + rest


def to_openai_tools(tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not tools:
        return []
    out = []
    for tdef in tools:
        if not isinstance(tdef, dict):
            continue
        if tdef.get("type") == "function" and "function" in tdef:
            fn = dict(tdef.get("function") or {})
            from Kerniq.models.text_tools import normalize_parameters

            fn["parameters"] = normalize_parameters(fn.get("parameters"))
            out.append({"type": "function", "function": fn})
            continue
        name = tdef.get("name") or ""
        params = tdef.get("input_schema") or tdef.get("parameters") or {
            "type": "object",
            "properties": {},
        }
        from Kerniq.models.text_tools import normalize_parameters

        out.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tdef.get("description") or "",
                    "parameters": normalize_parameters(params),
                },
            }
        )
    return out


def parse_openai_message(message: Dict[str, Any]) -> Message:
    content = message.get("content") or ""
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in (None, "text"):
                texts.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                texts.append(part)
        content = "".join(texts)
    reasoning = message.get("reasoning_content") or message.get("reasoning") or None
    tool_calls: List[ToolCall] = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args_raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
        except Exception:
            args = {"raw": args_raw}
        if isinstance(args, list):
            args = {"items": args}
        tool_calls.append(
            ToolCall(
                id=str(tc.get("id") or uuid.uuid4()),
                name=str(fn.get("name") or "unknown"),
                arguments=args if isinstance(args, dict) else {"raw": args},
            )
        )
    from Kerniq.models.text_tools import adopt_channel_calls

    content, adopted = adopt_channel_calls(content or "", tool_calls or None)
    tool_calls = list(adopted or [])
    return Message(
        role=MessageRole.ASSISTANT,
        content=content or "",
        tool_calls=tool_calls or None,
        metadata={"reasoning": reasoning} if reasoning else None,
    )


class OpenAICompatProvider(ModelProvider):
    def __init__(
        self,
        provider_id: str,
        base_url: str,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 600.0,
        extra_headers: Optional[Dict[str, str]] = None,
        label: str = "",
        requires_key: bool = True,
    ):
        self._provider_id = provider_id
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or None
        self.model = (model or "").strip() or None
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})
        self.label = label or provider_id
        self.requires_key = requires_key

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "tool_calls": True,
            "streaming": True,
            "vision": False,
            "reasoning": True,
        }

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.extra_headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _client(self) -> httpx.AsyncClient:
        t = float(self.timeout or 600.0)
        return httpx.AsyncClient(
            timeout=httpx.Timeout(connect=30.0, read=t, write=60.0, pool=30.0),
            trust_env=True,
            follow_redirects=True,
        )

    async def list_models(self) -> List[Dict[str, Any]]:
        if self.requires_key and not self.api_key:
            raise ProviderError(
                ErrorCode.AUTHENTICATION_ERROR,
                f"{self.label}: API key is required",
            )
        url = f"{self.base_url}/models"
        try:
            async with self._client() as client:
                response = await client.get(url, headers=self._headers())
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"{self.label} is unreachable at {url}: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(
                ErrorCode.AUTHENTICATION_ERROR,
                f"{self.label} rejected the API key ({response.status_code})",
            )
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"{self.label} models failed: {response.status_code} {response.text[:300]}",
            )
        try:
            data = response.json()
        except Exception as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"{self.label} models returned non-JSON",
                original_exception=exc,
            ) from exc
        rows = data.get("data") if isinstance(data, dict) else data
        if isinstance(data, dict) and not rows:
            rows = data.get("models") or []
        result = []
        from Kerniq.models.vision import model_sees_images

        for item in rows or []:
            if isinstance(item, str):
                result.append({"id": item, "name": item})
                continue
            if not isinstance(item, dict):
                continue
            mid = str(item.get("id") or item.get("name") or item.get("model") or "")
            if not mid:
                continue
            result.append(
                {
                    "id": mid,
                    "name": str(item.get("name") or mid),
                    "context_length": item.get("context_length")
                    or item.get("context_window")
                    or item.get("max_context_length"),
                    "type": item.get("type"),
                    "architecture": item.get("architecture"),
                    "capabilities": item.get("capabilities"),
                    "vision": model_sees_images(item),
                }
            )
        return result

    async def check_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception as exc:
            logger.error("%s connection check failed: %s", self.label, exc)
            return False

    async def _resolve_model(self) -> str:
        if self.model:
            return self.model
        models = await self.list_models()
        if not models:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"{self.label}: no model configured and the catalog is empty",
            )
        return str(models[0]["id"])

    async def generate(self, request: ModelRequest) -> ModelResponse:
        model = await self._resolve_model()
        payload: Dict[str, Any] = {
            "model": model,
            "messages": to_openai_messages(request.messages),
            "temperature": request.options.temperature if request.options else 0.7,
        }
        if request.options and request.options.max_tokens is not None:
            payload["max_tokens"] = request.options.max_tokens
        if request.options and request.options.extra_params:
            payload.update(request.options.extra_params)
        if (request.metadata or {}).get("kerniq_internal"):
            payload["enable_thinking"] = False
            payload["thinking"] = {"type": "disabled"}
            payload["reasoning_effort"] = "none"
        tools = to_openai_tools(request.tools)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        use_stream = bool(request.options and request.options.streaming)
        url = f"{self.base_url}/chat/completions"
        cancel_check = (request.metadata or {}).get("cancel_check")
        try:
            if use_stream:
                return await self._generate_stream(url, payload, request)
            async with self._client() as client:
                try:
                    response = await await_unless_cancelled(
                        client.post(url, json=payload, headers=self._headers()),
                        cancel_check,
                    )
                except StreamCancelled:
                    return cancelled_response()
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"{self.label} timed out",
                original_exception=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"{self.label} request failed: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(
                ErrorCode.AUTHENTICATION_ERROR,
                f"{self.label} rejected the API key ({response.status_code})",
            )
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"{self.label} chat error {response.status_code}: {response.text[:400]}",
            )
        data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = parse_openai_message(choice.get("message") or {})
        usage_raw = data.get("usage") or {}
        usage = None
        if usage_raw:
            usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        finish = choice.get("finish_reason") or ("tool_calls" if message.tool_calls else "stop")
        return ModelResponse(
            messages=[message],
            finish_reason=finish,
            usage=usage,
            request_id=data.get("id"),
            metadata={"api": self._provider_id, "model": data.get("model") or model},
        )

    async def _generate_stream(
        self, url: str, payload: Dict[str, Any], request: ModelRequest
    ) -> ModelResponse:
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        content_parts: List[str] = []
        tool_acc: Dict[int, Dict[str, str]] = {}
        finish_reason = None
        usage_raw: Dict[str, Any] = {}
        async with self._client() as client:
            async with client.stream(
                "POST",
                url,
                json=stream_payload,
                headers={**self._headers(), "Accept": "text/event-stream"},
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    text = body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body)
                    code = ErrorCode.AUTHENTICATION_ERROR if response.status_code in (401, 403) else ErrorCode.PROVIDER_REQUEST_FAILED
                    raise ProviderError(code, f"{self.label} stream error {response.status_code}: {text[:400]}")
                cancel_check = (request.metadata or {}).get("cancel_check")
                lines = response.aiter_lines()
                while True:
                    try:
                        line = await next_stream_line(lines, response, cancel_check)
                    except StreamCancelled:
                        return cancelled_response("".join(content_parts))
                    except StopAsyncIteration:
                        break
                    line = (line or "").strip()
                    if not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(chunk.get("usage"), dict):
                        usage_raw = chunk["usage"]
                    for choice in chunk.get("choices") or []:
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            content_parts.append(delta["content"])
                            cb = (request.metadata or {}).get("on_stream_delta")
                            if callable(cb):
                                try:
                                    cb({"type": "content", "text": delta["content"]})
                                except Exception:
                                    pass
                        rc = delta.get("reasoning_content") or delta.get("reasoning")
                        if rc:
                            cb = (request.metadata or {}).get("on_stream_delta")
                            if callable(cb):
                                try:
                                    cb({"type": "reasoning", "text": rc})
                                except Exception:
                                    pass
                        for tc in delta.get("tool_calls") or []:
                            idx = int(tc.get("index") or 0)
                            slot = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["name"] += fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"]
        tool_calls: List[ToolCall] = []
        for _, slot in sorted(tool_acc.items()):
            if not slot["name"]:
                continue
            try:
                args = json.loads(slot["arguments"] or "{}")
            except Exception:
                args = {"raw": slot["arguments"]}
            if isinstance(args, list):
                args = {"items": args}
            tool_calls.append(
                ToolCall(
                    id=slot["id"] or str(uuid.uuid4()),
                    name=slot["name"],
                    arguments=args if isinstance(args, dict) else {"raw": args},
                )
            )
        joined = "".join(content_parts)
        from Kerniq.models.text_tools import adopt_channel_calls

        joined, adopted = adopt_channel_calls(joined, tool_calls or None)
        tool_calls = list(adopted or [])
        usage = None
        if usage_raw:
            usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        return ModelResponse(
            messages=[
                Message(
                    role=MessageRole.ASSISTANT,
                    content=joined,
                    tool_calls=tool_calls or None,
                )
            ],
            finish_reason=finish_reason or ("tool_calls" if tool_calls else "stop"),
            usage=usage,
            metadata={"api": self._provider_id, "model": payload.get("model")},
        )
