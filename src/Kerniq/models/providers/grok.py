"""xAI Responses API. Not the legacy chat-completions path.

Grok reasoning models return an encrypted reasoning item next to the answer
and any function call. The next turn has to send that item back, or the model
forgets why it called the tool. Chat completions has no field for it.
"""

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

_SKIP_MODEL = ("imagine", "video", "embed", "tts", "audio", "image")


def _chat_model_id(model_id: str) -> bool:
    low = (model_id or "").lower()
    return bool(low) and not any(part in low for part in _SKIP_MODEL)


def to_grok_tools(tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    from .openai_compat import to_openai_tools

    flat: List[Dict[str, Any]] = []
    for item in to_openai_tools(tools):
        fn = item.get("function") or {}
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        flat.append(
            {
                "type": "function",
                "name": name,
                "description": fn.get("description") or "",
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        )
    return flat


def _text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
        return "".join(parts)
    return "" if content is None else str(content)


def _user_content(msg: Message) -> Any:
    from Kerniq.models.vision import openai_image_parts

    text = msg.content or ""
    images = openai_image_parts(getattr(msg, "metadata", None))
    if not images:
        return text
    parts: List[Dict[str, Any]] = []
    if text.strip():
        parts.append({"type": "input_text", "text": text})
    for image in images:
        url = ""
        if isinstance(image, dict):
            raw = image.get("image_url")
            url = raw.get("url") if isinstance(raw, dict) else str(raw or "")
        if url:
            parts.append({"type": "input_image", "image_url": url})
    return parts or text


def to_grok_input(messages: List[Message]) -> List[Dict[str, Any]]:
    """Responses `input`. A stored output array is replayed in order."""
    system_parts: List[str] = []
    items: List[Dict[str, Any]] = []
    for msg in messages:
        if msg.role == MessageRole.SYSTEM:
            text = (msg.content or "").strip()
            if text:
                system_parts.append(text)
            continue
        if msg.role == MessageRole.USER:
            items.append({"role": "user", "content": _user_content(msg)})
            continue
        if msg.role == MessageRole.ASSISTANT:
            raw = (msg.metadata or {}).get("grok_output") if isinstance(msg.metadata, dict) else None
            if isinstance(raw, list) and raw:
                items.extend(item for item in raw if isinstance(item, dict))
                continue
            if (msg.content or "").strip():
                items.append({"role": "assistant", "content": msg.content or ""})
            for tc in msg.tool_calls or []:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.id,
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments or {}, ensure_ascii=False),
                    }
                )
            continue
        if msg.role == MessageRole.TOOL:
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id or "",
                    "output": msg.content or "",
                }
            )
    if system_parts:
        items.insert(0, {"role": "system", "content": "\n\n".join(system_parts)})
    return items


def build_responses_payload(
    messages: List[Message],
    tools: Optional[List[Dict[str, Any]]],
    model: str,
    *,
    temperature: float = 0.7,
    top_p: Optional[float] = None,
    max_output_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "input": to_grok_input(messages),
        "temperature": temperature,
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    if top_p is not None:
        payload["top_p"] = top_p
    if max_output_tokens is not None:
        payload["max_output_tokens"] = int(max_output_tokens)
    grok_tools = to_grok_tools(tools)
    if grok_tools:
        payload["tools"] = grok_tools
        payload["tool_choice"] = "auto"
    return payload


def _reasoning_text(item: Dict[str, Any]) -> str:
    summary = item.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    chunks: List[str] = []
    if isinstance(summary, list):
        for part in summary:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                chunks.append(str(part.get("text") or ""))
    text = item.get("content") or item.get("text")
    if isinstance(text, str):
        chunks.append(text)
    elif isinstance(text, list):
        chunks.append(_text_content(text))
    return "".join(chunks).strip()


def parse_responses_body(data: Dict[str, Any]) -> Message:
    output = data.get("output") if isinstance(data, dict) else None
    if not isinstance(output, list):
        output = []
    texts: List[str] = []
    reasoning: List[str] = []
    tool_calls: List[ToolCall] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        if kind == "reasoning":
            note = _reasoning_text(item)
            if note:
                reasoning.append(note)
            continue
        if kind == "function_call":
            args_raw = item.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except Exception:
                args = {"raw": args_raw}
            if isinstance(args, list):
                args = {"items": args}
            if not isinstance(args, dict):
                args = {"raw": args}
            tool_calls.append(
                ToolCall(
                    id=str(item.get("call_id") or item.get("id") or uuid.uuid4()),
                    name=str(item.get("name") or "unknown"),
                    arguments=args,
                )
            )
            continue
        if kind in ("message", "output_text"):
            content = item.get("content")
            if kind == "output_text":
                texts.append(_text_content(item.get("text") or content))
            else:
                texts.append(_text_content(content))
    if not texts:
        fallback = data.get("output_text") if isinstance(data, dict) else None
        if isinstance(fallback, str) and fallback.strip():
            texts.append(fallback)
    meta: Dict[str, Any] = {}
    if reasoning:
        meta["reasoning"] = "\n".join(reasoning)
    if output:
        meta["grok_output"] = [item for item in output if isinstance(item, dict)]
    return Message(
        role=MessageRole.ASSISTANT,
        content="".join(texts),
        tool_calls=tool_calls or None,
        metadata=meta or None,
    )


def _usage(data: Dict[str, Any]) -> Optional[TokenUsage]:
    raw = data.get("usage") if isinstance(data, dict) else None
    if not isinstance(raw, dict) or not raw:
        return None
    return TokenUsage(
        prompt_tokens=raw.get("input_tokens") if raw.get("input_tokens") is not None else raw.get("prompt_tokens"),
        completion_tokens=raw.get("output_tokens") if raw.get("output_tokens") is not None else raw.get("completion_tokens"),
        total_tokens=raw.get("total_tokens"),
    )


def _finish(data: Dict[str, Any], message: Message) -> str:
    if message.tool_calls:
        return "tool_calls"
    status = str((data or {}).get("status") or "").lower()
    if status in ("incomplete", "failed", "cancelled"):
        return "length" if status == "incomplete" else "stop"
    return "stop"


class GrokProvider(ModelProvider):
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://api.x.ai/v1",
        timeout: float = 600.0,
    ):
        self.api_key = api_key or None
        self.model = (model or "").strip() or None
        self.base_url = (base_url or "https://api.x.ai/v1").rstrip("/")
        self.timeout = timeout
        self.label = "Grok"

    @property
    def provider_id(self) -> str:
        return "grok"

    def get_capabilities(self) -> Dict[str, Any]:
        return {"tool_calls": True, "streaming": True, "vision": True, "reasoning": True}

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
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

    def _require_key(self) -> None:
        if not self.api_key:
            raise ProviderError(ErrorCode.AUTHENTICATION_ERROR, "Grok: API key is required")

    async def list_models(self) -> List[Dict[str, Any]]:
        self._require_key()
        url = f"{self.base_url}/models"
        try:
            async with self._client() as client:
                response = await client.get(url, headers=self._headers())
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Grok is unreachable at {url}: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(
                ErrorCode.AUTHENTICATION_ERROR,
                f"Grok rejected the API key ({response.status_code})",
            )
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"Grok models failed: {response.status_code} {response.text[:300]}",
            )
        try:
            data = response.json()
        except Exception as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                "Grok models returned non-JSON",
                original_exception=exc,
            ) from exc
        rows = data.get("data") if isinstance(data, dict) else data
        if isinstance(data, dict) and not rows:
            rows = data.get("models") or []
        result = []
        from Kerniq.models.vision import model_sees_images

        for item in rows or []:
            if isinstance(item, str):
                mid = item
                record: Dict[str, Any] = {"id": mid}
            elif isinstance(item, dict):
                mid = str(item.get("id") or item.get("name") or "")
                record = item
            else:
                continue
            if not mid or not _chat_model_id(mid):
                continue
            result.append(
                {
                    "id": mid,
                    "name": str(record.get("name") or mid) if isinstance(record, dict) else mid,
                    "context_length": record.get("context_length") or record.get("context_window"),
                    "type": record.get("type"),
                    "architecture": record.get("architecture"),
                    "capabilities": record.get("capabilities"),
                    "vision": model_sees_images(record) if isinstance(record, dict) else False,
                }
            )
        return result

    async def check_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception as exc:
            logger.error("Grok connection check failed: %s", exc)
            return False

    async def _resolve_model(self) -> str:
        if self.model:
            return self.model
        models = await self.list_models()
        if not models:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                "Grok: no model configured and the catalog is empty",
            )
        return str(models[0]["id"])

    def _payload(self, request: ModelRequest, model: str) -> Dict[str, Any]:
        options = request.options
        return build_responses_payload(
            request.messages,
            request.tools,
            model,
            temperature=options.temperature if options else 0.7,
            top_p=options.top_p if options else None,
            max_output_tokens=options.max_tokens if options and options.max_tokens is not None else None,
        )

    def _response(self, data: Dict[str, Any], model: str) -> ModelResponse:
        message = parse_responses_body(data)
        return ModelResponse(
            messages=[message],
            finish_reason=_finish(data, message),
            usage=_usage(data),
            request_id=str(data.get("id") or "") or None,
            metadata={"api": "grok", "model": data.get("model") or model},
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        self._require_key()
        model = await self._resolve_model()
        payload = self._payload(request, model)
        url = f"{self.base_url}/responses"
        cancel_check = (request.metadata or {}).get("cancel_check")
        use_stream = bool(request.options and request.options.streaming)
        try:
            if use_stream:
                return await self._generate_stream(url, payload, request, model)
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
            raise ProviderError(ErrorCode.PROVIDER_REQUEST_FAILED, "Grok timed out", original_exception=exc) from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Grok request failed: {exc}",
                original_exception=exc,
            ) from exc
        if response.status_code in (401, 403):
            raise ProviderError(
                ErrorCode.AUTHENTICATION_ERROR,
                f"Grok rejected the API key ({response.status_code})",
            )
        if response.status_code >= 400:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"Grok responses error {response.status_code}: {response.text[:400]}",
            )
        try:
            data = response.json()
        except Exception as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                "Grok returned non-JSON",
                original_exception=exc,
            ) from exc
        return self._response(data if isinstance(data, dict) else {}, model)

    async def _generate_stream(
        self, url: str, payload: Dict[str, Any], request: ModelRequest, model: str
    ) -> ModelResponse:
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        completed: Optional[Dict[str, Any]] = None
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
                    code = (
                        ErrorCode.AUTHENTICATION_ERROR
                        if response.status_code in (401, 403)
                        else ErrorCode.PROVIDER_REQUEST_FAILED
                    )
                    raise ProviderError(code, f"Grok stream error {response.status_code}: {text[:400]}")
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
                    if not data_text or data_text == "[DONE]":
                        if data_text == "[DONE]":
                            break
                        continue
                    try:
                        event = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(event, dict):
                        continue
                    kind = str(event.get("type") or "")
                    if kind == "error" or event.get("error"):
                        err = event.get("error")
                        detail = err.get("message") if isinstance(err, dict) else err
                        raise ProviderError(
                            ErrorCode.PROVIDER_REQUEST_FAILED,
                            f"Grok stream error: {detail or event}",
                        )
                    if kind in ("response.completed", "response.incomplete", "response.failed"):
                        body = event.get("response")
                        if isinstance(body, dict):
                            completed = body
                        continue
                    delta = event.get("delta")
                    if kind in ("response.output_text.delta", "response.output_text.done") and isinstance(delta, str):
                        if kind.endswith(".delta"):
                            content_parts.append(delta)
                            cb = (request.metadata or {}).get("on_stream_delta")
                            if callable(cb):
                                try:
                                    cb({"type": "content", "text": delta})
                                except Exception:
                                    pass
                    elif kind in (
                        "response.reasoning_summary_text.delta",
                        "response.reasoning_text.delta",
                    ) and isinstance(delta, str):
                        reasoning_parts.append(delta)
                        cb = (request.metadata or {}).get("on_stream_delta")
                        if callable(cb):
                            try:
                                cb({"type": "reasoning", "text": delta})
                            except Exception:
                                pass
        if completed:
            built = self._response(completed, model)
            message = built.messages[0]
            if not (message.content or "").strip() and content_parts:
                message.content = "".join(content_parts)
            if isinstance(message.metadata, dict) and reasoning_parts and not message.metadata.get("reasoning"):
                message.metadata["reasoning"] = "".join(reasoning_parts)
            return built
        meta: Dict[str, Any] = {"api": "grok", "model": model}
        msg_meta: Dict[str, Any] = {}
        if reasoning_parts:
            msg_meta["reasoning"] = "".join(reasoning_parts)
        return ModelResponse(
            messages=[
                Message(
                    role=MessageRole.ASSISTANT,
                    content="".join(content_parts),
                    metadata=msg_meta or None,
                )
            ],
            finish_reason="stop",
            metadata=meta,
        )
