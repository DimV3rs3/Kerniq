"""LM Studio provider.

Model catalog, load, and unload use the native LMS API (``/api/v1/...``).
Chat and tool calls use the OpenAI-compatible endpoint
``/v1/chat/completions``, which is what current LM Studio builds expose for
tools. ``/api/v1/chat`` is not used for generation.

On Windows, system HTTP_PROXY often breaks localhost. Local hosts set
``trust_env=False``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from typing import Dict, Any, Optional, List, Tuple

import httpx

from ...interfaces.providers import ModelProvider
from ...interfaces.models import (
    ModelRequest,
    ModelResponse,
    Message,
    MessageRole,
    TokenUsage,
    ToolCall,
)
from ...interfaces.errors import ProviderError, ErrorCode
from ..cancel import StreamCancelled, await_unless_cancelled, cancelled_response, next_stream_line

logger = logging.getLogger(__name__)

# Back-to-back UI polls (loaded + catalog) must not hit /api/v1/models twice.
_LIST_CACHE: Dict[str, Any] = {"key": None, "at": 0.0, "data": None}
_LIST_TTL = 2.0


def _invalidate_model_cache() -> None:
    _LIST_CACHE["at"] = 0.0
    _LIST_CACHE["data"] = None


def _normalize_host(base_url: str) -> str:
    url = (base_url or "http://localhost:1234").rstrip("/")
    for suffix in ("/api/v1", "/api/v0", "/v1", "/v0"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url.rstrip("/")


def _is_local_host(host: str) -> bool:
    """Local and private addresses must not go through an HTTP proxy."""
    h = (host or "").lower()
    if (
        "localhost" in h
        or "127.0.0.1" in h
        or "[::1]" in h
        or h.startswith("http://0.0.0.0")
        or h.startswith("https://0.0.0.0")
    ):
        return True
    start = h.find("://")
    name = h[start + 3:] if start >= 0 else h
    name = name.split("/", 1)[0].split(":", 1)[0].strip("[]")
    parts = name.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    a, b = int(parts[0]), int(parts[1])
    if a == 10 or a == 192 and b == 168:
        return True
    return a == 172 and 16 <= b <= 31


def _number(value: Any) -> Optional[float]:
    """Positive number from an int, float, or a string like ``4.2 GB``."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([kmgt]?b)?", text, flags=re.I)
    if not match:
        return None
    amount = float(match.group(1))
    unit = (match.group(2) or "").lower()
    scale = {"": 1, "b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3, "tb": 1024 ** 4}
    return amount * scale.get(unit, 1)


def _size_bytes(payload: Dict[str, Any]) -> Optional[int]:
    """On-disk weight. LM Studio reports ``size_bytes`` on ``/api/v1/models``."""
    keys = (
        "size_bytes", "sizeBytes", "file_size", "fileSize",
        "model_size_bytes", "bytes", "size",
    )
    for source in (payload, payload.get("info"), payload.get("metadata"), payload.get("stats")):
        if not isinstance(source, dict):
            continue
        for key in keys:
            amount = _number(source.get(key))
            if amount is None:
                continue
            # A bare ``size: 7`` is a parameter count, not a file.
            if key == "size" and amount < 10_000:
                continue
            return int(amount)
    return None


def _param_count(payload: Dict[str, Any]) -> Optional[float]:
    """Parameter count. Prefers an explicit field, then ``7B`` / ``8x7B`` in the name."""
    for source in (payload, payload.get("info"), payload.get("metadata")):
        if not isinstance(source, dict):
            continue
        for key in ("parameter_count", "params", "n_params", "param_count"):
            amount = _number(source.get(key))
            if amount is None:
                continue
            return amount * 1e9 if amount < 10_000 else amount
        text = str(source.get("params_string") or source.get("paramsString") or "").strip()
        parsed = _params_in_text(text)
        if parsed:
            return parsed
    blob = " ".join(
        str(payload.get(key) or "")
        for key in ("key", "id", "name", "display_name", "path")
    )
    return _params_in_text(blob)


def _params_in_text(text: str) -> Optional[float]:
    if not text:
        return None
    moe = re.search(r"(?i)(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*b\b", text)
    if moe:
        return float(moe.group(1)) * float(moe.group(2)) * 1e9
    found = [
        float(match.group(1)) * (1e9 if match.group(2).lower() == "b" else 1e6)
        for match in re.finditer(r"(?i)(?:^|[^a-z0-9])(?:e)?(\d+(?:\.\d+)?)\s*([bm])\b", text)
    ]
    return max(found) if found else None


def _quant_bits(payload: Dict[str, Any]) -> float:
    quant = payload.get("quantization")
    name = ""
    if isinstance(quant, dict):
        bits = _number(quant.get("bits_per_weight") if quant.get("bits_per_weight") is not None else quant.get("bits"))
        if bits and bits <= 32:
            return float(bits)
        name = str(quant.get("name") or "")
    elif quant:
        name = str(quant)
    blob = name + " " + " ".join(str(payload.get(key) or "") for key in ("id", "key", "name", "display_name"))
    if re.search(r"(?i)\b(bf16|fp16|f16)\b", blob):
        return 16.0
    if re.search(r"(?i)\b(fp32|f32)\b", blob):
        return 32.0
    match = re.search(r"(?i)\b(?:iq|q|int|fp|bf|f)(\d{1,2})\b", blob)
    if match:
        bits = int(match.group(1))
        if 1 <= bits <= 32:
            return float(bits)
    return 4.5


def estimate_weight(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Bytes of the weights, plus the parameter count when LM Studio (or the name) has it.

    ``size_bytes`` wins. Otherwise parameters × quantisation bits.
    """
    if not isinstance(payload, dict):
        return {"size_bytes": None, "params": None, "weight_bytes": 0}
    raw = payload.get("raw") if isinstance(payload.get("raw"), dict) else payload
    size = _size_bytes(raw)
    if size is None:
        size = _size_bytes(payload)
    params = _param_count(raw)
    if params is None:
        params = _param_count(payload)
    weight = size
    if not weight and params:
        weight = int(params * _quant_bits(raw) / 8.0)
    return {
        "size_bytes": int(size) if size else None,
        "params": float(params) if params else None,
        "weight_bytes": int(weight or 0),
    }


def instance_ids_for_unload(instances: List[Dict[str, Any]], model_id: str) -> List[str]:
    """Instance ids accepted by ``POST /api/v1/models/unload``.

    The first loaded copy uses the catalog key as its id
    (``google/gemma-4-e2b``). The next copy is ``key:2``. Both are real
    instance ids. Treating the catalog key as "not an instance" skips the
    unload, then the following load sees the model still loaded and leaves it.
    """
    from Kerniq.models.identity import instance_model_key, same_model

    want = instance_model_key(model_id)
    if not want:
        return []
    found: List[str] = []
    for item in instances or []:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("instance_id") or item.get("id") or "").strip()
        catalog = instance_model_key(str(item.get("model") or raw))
        if not same_model(catalog, want):
            continue
        iid = raw or want
        if iid and iid not in found:
            found.append(iid)
    return found


class LMStudioProvider(ModelProvider):
    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        api_key: Optional[str] = None,
        timeout: float = 600.0,
        model: Optional[str] = None,
    ):
        self.host = _normalize_host(base_url)
        # Token: explicit arg → env LM_API_TOKEN / LMS_API_TOKEN
        self.api_key = (
            api_key
            or os.environ.get("LM_API_TOKEN")
            or os.environ.get("LMS_API_TOKEN")
            or os.environ.get("LM_STUDIO_API_TOKEN")
        )
        self.timeout = timeout
        self.model = model
        self.models_path = "/api/v1/models"
        self.chat_path = "/api/v1/chat"

    @property
    def base_url(self) -> str:
        return self.host

    @property
    def provider_id(self) -> str:
        return "lm_studio"

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self.host}{path}"

    def _client(self, timeout: Optional[float] = None) -> httpx.AsyncClient:
        # Critical on Windows: do NOT use system proxy for local LMS.
        # Use split timeouts: long *read* so prefill/reasoning can take minutes–hours
        # without killing the whole stream (default scalar timeout is total wall time).
        t = float(timeout if timeout is not None else self.timeout)
        if t <= 0:
            t = 600.0
        http_timeout = httpx.Timeout(
            connect=30.0,
            read=t,
            write=60.0,
            pool=30.0,
        )
        return httpx.AsyncClient(
            timeout=http_timeout,
            trust_env=not _is_local_host(self.host),
            follow_redirects=True,
        )

    async def _get_json(self, path: str, timeout: float = 15.0) -> Tuple[Any, str]:
        url = self._url(path)
        async with self._client(timeout=timeout) as client:
            response = await client.get(url, headers=self._headers())
            body = response.text
            if response.status_code >= 400:
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED
                    if response.status_code != 503
                    else ErrorCode.PROVIDER_UNAVAILABLE,
                    f"LM Studio {url} error: {response.status_code} {body[:500]}",
                )
            try:
                return response.json(), url
            except Exception as e:
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    f"LM Studio {url} returned non-JSON: {body[:300]}",
                    original_exception=e,
                ) from e

    async def check_connection(self) -> bool:
        try:
            await self.list_models()
            return True
        except Exception as e:
            logger.error("Connection check failed for LM Studio: %s", e)
            return False

    async def list_models(self) -> List[Dict[str, Any]]:
        key = (self.host, bool(self.api_key))
        now = time.monotonic()
        cached = _LIST_CACHE.get("data")
        if (
            _LIST_CACHE.get("key") == key
            and cached is not None
            and (now - float(_LIST_CACHE.get("at") or 0)) < _LIST_TTL
        ):
            return list(cached)
        data, url = await self._get_json(self.models_path)
        logger.info("LM Studio models OK via %s", url)
        parsed = self._parse_models_payload(data)
        _LIST_CACHE["key"] = key
        _LIST_CACHE["at"] = now
        _LIST_CACHE["data"] = parsed
        return list(parsed)

    def _parse_models_payload(self, data: Any) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        models: List[Any] = []
        if isinstance(data, dict):
            models = data.get("models") or data.get("data") or []
        elif isinstance(data, list):
            models = data

        for m in models:
            if not isinstance(m, dict):
                result.append({"id": str(m), "name": str(m)})
                continue
            mid = m.get("key") or m.get("id") or m.get("name")
            # max_context_length = model capability; loaded config.context_length = actual window
            max_ctx = m.get("max_context_length") or m.get("max_context") or None
            loaded_ctx = None
            for inst in (m.get("loaded_instances") or []):
                if not isinstance(inst, dict):
                    continue
                cfg = inst.get("config") or {}
                if isinstance(cfg, dict) and cfg.get("context_length"):
                    loaded_ctx = int(cfg["context_length"])
                    break
            # Prefer loaded window for fill %; fall back to max
            effective = loaded_ctx or max_ctx
            weight = estimate_weight(m)
            from Kerniq.models.vision import model_sees_images

            result.append(
                {
                    "id": mid,
                    "name": m.get("display_name") or mid,
                    "type": m.get("type"),
                    "architecture": m.get("architecture"),
                    "capabilities": m.get("capabilities"),
                    "quantization": m.get("quantization"),
                    "loaded_instances": m.get("loaded_instances"),
                    "max_context_length": int(max_ctx) if max_ctx else None,
                    "context_length": int(effective) if effective else None,
                    "loaded_context_length": loaded_ctx,
                    "size_bytes": weight["size_bytes"],
                    "params": weight["params"],
                    "weight_bytes": weight["weight_bytes"],
                    "vision": model_sees_images(m),
                    "raw": m,
                }
            )
        return result

    async def health_report(self) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "provider": self.provider_id,
            "host": self.host,
            "models_url": self._url(self.models_path),
            "chat_url": self._url("/v1/chat/completions"),
            "native_chat_url": self._url(self.chat_path),
            "api": "lms /api/v1",
            "auth": bool(self.api_key),
            "trust_env_proxy": not _is_local_host(self.host),
            "reachable": False,
            "models": [],
            "selected_model": self.model,
            "error": None,
            "hint": None,
        }
        try:
            report["models"] = await self.list_models()
            report["reachable"] = True
            ids = [m.get("id") for m in report["models"]]
            if self.model and self.model not in ids:
                report["error"] = f"Configured model '{self.model}' not in catalog"
            elif not self.model and ids:
                preferred = None
                for m in report["models"]:
                    if m.get("loaded_instances"):
                        preferred = m.get("id")
                        break
                report["selected_model"] = preferred or ids[0]
        except Exception as e:
            report["error"] = str(e)
            err = str(e)
            hints = []
            if "503" in err:
                hints.append(
                    "503: LMS server not ready, or wrong endpoint. "
                    "In LM Studio open Developer → Start Server. "
                    "Check in browser: " + self._url(self.models_path)
                )
                hints.append(
                    "If browser works but app does not: disable system proxy for localhost "
                    "(we already set trust_env=False for local hosts)."
                )
            if "401" in err or "403" in err:
                hints.append(
                    "Auth required: set LM_API_TOKEN env var to token from LM Studio Developer page."
                )
            if "ConnectError" in err or "refused" in err.lower():
                hints.append("Connection refused: server not listening on " + self.host)
            report["hint"] = " | ".join(hints) if hints else None
        return report

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "tool_calls": True,
            "streaming": True,
            "vision": False,
            "reasoning": True,
            "list_models": True,
            "load_model": True,
            "api": "openai_compat_/v1/chat/completions",
            "native_model_api": "lms_/api/v1/models",
            "notes": (
                "Tool calls and streaming are implemented on /v1/chat/completions. "
                "Model load/unload uses /api/v1. Context length is taken from the "
                "catalog when LM Studio reports it; otherwise Kerniq uses a labelled estimate."
            ),
        }


    def _parse_chat_response(self, data: Dict[str, Any]) -> ModelResponse:
        outputs = data.get("output") or []
        text_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for item in outputs:
            if not isinstance(item, dict):
                continue
            itype = item.get("type")
            if itype in ("reasoning", "thinking"):
                reasoning_parts.append(item.get("content") or "")
            elif itype == "message":
                text_parts.append(item.get("content") or "")
            elif itype == "tool_call":
                name = item.get("tool") or item.get("name") or "unknown"
                args = item.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw": args}
                # Incomplete tool call text sometimes appears inside message content
                tc_id = str(item.get("id") or uuid.uuid4())
                if item.get("output"):
                    text_parts.append(f"[tool {name} result]: {item.get('output')}")
                else:
                    tool_calls.append(ToolCall(id=tc_id, name=name, arguments=args))
            elif item.get("content"):
                text_parts.append(str(item["content"]))

        # Also parse tool calls embedded in message text (incomplete generation)
        content = "\n".join(p for p in text_parts if p).strip()
        if not tool_calls and content:
            import re
            m = re.search(r"(?:call:|tool_call[:\s]*)([a-zA-Z0-9_]+)[{\s]", content)
            # leave as text if incomplete


        # Prompt-based tool protocol: <tool_call>{"name":..., "arguments":...}</tool_call>
        if not tool_calls and content:
            import re as _re
            for m in _re.finditer(
                r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
                content,
                flags=_re.S | _re.I,
            ):
                try:
                    obj = json.loads(m.group(1))
                    tool_calls.append(
                        ToolCall(
                            id=str(uuid.uuid4()),
                            name=str(obj.get("name") or "unknown"),
                            arguments=obj.get("arguments") or {},
                        )
                    )
                except Exception:
                    pass
            if tool_calls:
                content = _re.sub(
                    r"<tool_call>\s*\{.*?\}\s*</tool_call>",
                    "",
                    content,
                    flags=_re.S | _re.I,
                ).strip()

        assistant = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or None,
            metadata={"reasoning": "\n".join(reasoning_parts) if reasoning_parts else None},
        )
        stats = data.get("stats") or {}
        usage = None
        if stats:
            usage = TokenUsage(
                prompt_tokens=stats.get("input_tokens"),
                completion_tokens=stats.get("total_output_tokens"),
                total_tokens=(
                    (stats.get("input_tokens") or 0)
                    + (stats.get("total_output_tokens") or 0)
                )
                or None,
            )
        finish = "tool_calls" if tool_calls else "stop"
        meta = {
            "raw": data,
            "api": "lms /api/v1/chat",
            "reasoning": "\n".join(reasoning_parts) if reasoning_parts else None,
            "tokens_per_second": stats.get("tokens_per_second"),
            "model_instance_id": data.get("model_instance_id"),
        }
        return ModelResponse(
            messages=[assistant],
            finish_reason=finish,
            usage=usage,
            request_id=data.get("response_id") or data.get("model_instance_id"),
            metadata=meta,
        )


    async def loaded_instances(self) -> List[Dict[str, Any]]:
        models = await self.list_models()
        loaded: List[Dict[str, Any]] = []
        for m in models:
            raw = m.get("raw") or m
            for inst in (raw.get("loaded_instances") or m.get("loaded_instances") or []):
                item = dict(inst) if isinstance(inst, dict) else {"value": inst}
                from Kerniq.models.identity import instance_model_key

                catalog = instance_model_key(str(m.get("id") or ""))
                raw_id = str(item.get("model") or item.get("id") or catalog)
                item["model"] = instance_model_key(raw_id) or catalog
                if not item.get("instance_id"):
                    inst_id = item.get("id")
                    # The catalog key is the instance id of the first loaded copy.
                    if inst_id:
                        item["instance_id"] = str(inst_id)
                loaded.append(item)
        return loaded

    async def unload_model(self, instance_id: str) -> Dict[str, Any]:
        url = self._url("/api/v1/models/unload")
        async with self._client(timeout=300) as client:
            r = await client.post(url, json={"instance_id": instance_id}, headers=self._headers())
            if r.status_code >= 400:
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    f"Unload failed: {r.status_code} {r.text[:300]}",
                )
            _invalidate_model_cache()
            return r.json() if r.content else {}

    async def unload_all(self) -> List[Dict[str, Any]]:
        results = []
        for item in await self.loaded_instances():
            iid = item.get("instance_id") or item.get("id")
            if not iid:
                continue
            results.append(await self.unload_model(str(iid)))
        return results

    async def model_is_loaded(self, model_key: str) -> bool:
        """True when this catalog key already has a loaded instance.

        A second copy (``model:2``) counts. A different sibling does not.
        """
        from Kerniq.models.identity import instance_model_key, same_model

        want = instance_model_key(model_key)
        if not want:
            return False
        for item in await self.loaded_instances():
            if same_model(str(item.get("model") or ""), want):
                return True
        return False

    async def load_model(self, model_key: str, context_length: Optional[int] = None) -> Dict[str, Any]:
        if await self.model_is_loaded(model_key):
            logger.info("load skipped, already loaded: %s", model_key)
            return {"ok": True, "already_loaded": True, "model": model_key}
        payload: Dict[str, Any] = {"model": model_key}
        if context_length is not None:
            payload["context_length"] = context_length
        url = self._url("/api/v1/models/load")
        async with self._client(timeout=600) as client:
            r = await client.post(url, json=payload, headers=self._headers())
            if r.status_code >= 400:
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    f"Load failed: {r.status_code} {r.text[:400]}",
                )
            _invalidate_model_cache()
            return r.json() if r.content else {}

    async def embed_text(self, model: str, text: str) -> List[float]:
        """Run a prompt through an embedding model. Returns the vector, or []."""
        url = self._url("/v1/embeddings")
        payload = {"model": model, "input": (text or "")[:2000]}
        async with self._client(timeout=120) as client:
            response = await client.post(url, json=payload, headers=self._headers())
            if response.status_code >= 400:
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    f"Embeddings failed: {response.status_code} {response.text[:300]}",
                )
            data = response.json() if response.content else {}
        rows = data.get("data") or []
        if not rows or not isinstance(rows[0], dict):
            return []
        vector = rows[0].get("embedding") or []
        return list(vector) if isinstance(vector, list) else []

    async def unload_model_instances(self, model_id: str) -> List[Dict[str, Any]]:
        """Unload every loaded instance of one model. Other models stay loaded."""
        from Kerniq.models.identity import instance_model_key

        want = instance_model_key(model_id)
        if not want:
            return []
        results: List[Dict[str, Any]] = []
        for iid in instance_ids_for_unload(await self.loaded_instances(), want):
            results.append(await self.unload_model(str(iid)))
        return results

    def _to_openai_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        from .openai_compat import to_openai_messages

        return to_openai_messages(messages)

    def _to_openai_tools(self, tools: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
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
            name = tdef.get("name") or tdef.get("tool") or ""
            desc = tdef.get("description") or ""
            params = tdef.get("input_schema") or tdef.get("parameters") or {"type": "object", "properties": {}}
            from Kerniq.models.text_tools import normalize_parameters

            out.append({
                "type": "function",
                "function": {"name": name, "description": desc, "parameters": normalize_parameters(params)},
            })
        return out

    def _parse_openai_completion(self, data: Dict[str, Any]) -> ModelResponse:
        choices = data.get("choices") or []
        choice = choices[0] if choices else {}
        message = choice.get("message") or {}
        content = message.get("content") or ""
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
        assistant = Message(
            role=MessageRole.ASSISTANT,
            content=content or "",
            tool_calls=tool_calls or None,
            metadata={"reasoning": reasoning} if reasoning else None,
        )
        usage_raw = data.get("usage") or {}
        usage = None
        if usage_raw:
            usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        finish = choice.get("finish_reason") or ("tool_calls" if tool_calls else "stop")
        return ModelResponse(
            messages=[assistant],
            finish_reason=finish,
            usage=usage,
            request_id=data.get("id"),
            metadata={
                "api": "openai_compat /v1/chat/completions",
                "reasoning": reasoning,
                "model": data.get("model"),
                "raw": data,
            },
        )


    def _friendly_chat_error(self, status: int, body: str, url: str) -> str:
        b = (body or "").lower()
        if status in (400, 404) and any(x in b for x in ("not loaded", "no model", "model_not", "unload", "not found")):
            return (
                "Model is not loaded in LM Studio. Load a model in LM Studio "
                "(or use Kerniq → API & model → Refresh / load), then try again."
            )
        if status == 404:
            return f"LM Studio endpoint not found ({url}). Is the local server running?"
        if status >= 500:
            return f"LM Studio server error ({status}). The model may have crashed or been unloaded."
        return f"LM Studio chat error ({url}): {status} {body[:400]}"


    async def resolve_auto_model(self) -> Optional[str]:
        """Pick a model when settings say (auto).

        Priority:
        1. First *loaded* LLM (skip embeddings)
        2. First catalog LLM that has loaded_instances
        3. First catalog LLM, even if it is not loaded yet
        """
        try:
            models = await self.list_models()
        except Exception as e:
            logger.warning("resolve_auto_model: list_models failed: %s", e)
            return None
        if not models:
            return None

        def is_llm(m: Dict[str, Any]) -> bool:
            t = (m.get("type") or "").lower()
            if t in ("embedding", "embeddings", "reranker"):
                return False
            name = str(m.get("id") or m.get("name") or "").lower()
            if "embed" in name:
                return False
            return True

        # Prefer explicitly loaded
        for m in models:
            if not is_llm(m):
                continue
            inst = m.get("loaded_instances") or []
            if inst:
                mid = m.get("id")
                if mid:
                    logger.info("auto model -> loaded %s", mid)
                    return str(mid)
        # Also check list_loaded if available
        try:
            loaded = await self.loaded_instances()
            for item in loaded or []:
                mid = item.get("model") or item.get("id") or item.get("key")
                if mid and "embed" not in str(mid).lower():
                    logger.info("auto model -> list_loaded %s", mid)
                    return str(mid)
        except Exception:
            pass
        for m in models:
            if not is_llm(m):
                continue
            mid = m.get("id")
            if mid:
                logger.info("auto model -> first catalog %s", mid)
                return str(mid)
        return None

    async def generate(self, request: ModelRequest) -> ModelResponse:
        """Chat via OpenAI-compatible /v1/chat/completions (same as benchmark/analyzer).

        Model list/load/unload stay on /api/v1/*. Custom tools work only on /v1/chat/completions.
        """
        meta = request.metadata or {}
        model = (self.model or meta.get("model") or "").strip() or None
        if not model:
            model = await self.resolve_auto_model()
        if not model:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                "No model specified (settings = auto) and no loaded LLM found in LM Studio. "
                "Load a model in LM Studio or pick one under API & model.",
            )

        payload: Dict[str, Any] = {
            "model": model,
            "messages": self._to_openai_messages(request.messages),
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
        oai_tools = self._to_openai_tools(request.tools)
        if oai_tools:
            payload["tools"] = oai_tools
            payload["tool_choice"] = "auto"

        use_stream = bool(request.options and request.options.streaming)
        url = self._url("/v1/chat/completions")
        cancel_check = (request.metadata or {}).get("cancel_check")

        try:
            if use_stream:
                return await self._generate_stream(url, payload, request)
            async with self._client(timeout=self.timeout) as client:
                try:
                    response = await await_unless_cancelled(
                        client.post(url, json=payload, headers=self._headers()),
                        cancel_check,
                    )
                except StreamCancelled:
                    return cancelled_response()
                body = response.text
                if response.status_code >= 400:
                    raise ProviderError(
                        ErrorCode.PROVIDER_REQUEST_FAILED,
                        self._friendly_chat_error(response.status_code, body, url),
                    )
                data = response.json()
        except ProviderError:
            raise
        except httpx.TimeoutException as e:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"LM Studio chat timeout after {self.timeout}s at {url}. ({e})",
                original_exception=e,
            ) from e
        except httpx.RequestError as e:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Failed to connect to LM Studio chat at {url}: {e}",
                original_exception=e,
            ) from e
        except Exception as e:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"LM Studio chat failed: {e}",
                original_exception=e,
            ) from e

        return self._parse_openai_completion(data)

    async def _generate_stream(
        self, url: str, payload: Dict[str, Any], request: ModelRequest
    ) -> ModelResponse:
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        stream_payload["stream_options"] = {"include_usage": True}
        import time as _time
        content_parts: List[str] = []
        reasoning_parts: List[str] = []
        tool_acc: Dict[int, Dict[str, Any]] = {}
        usage_raw: Dict[str, Any] = {}
        finish_reason = None
        response_id = None
        model_name = None
        stream_started = _time.monotonic()
        first_token_at = None
        gen_tokens = 0

        async with self._client(timeout=self.timeout) as client:
            async with client.stream(
                "POST", url, json=stream_payload, headers={**self._headers(), "Accept": "text/event-stream"}
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderError(
                        ErrorCode.PROVIDER_REQUEST_FAILED,
                        self._friendly_chat_error(response.status_code, body.decode("utf-8", errors="replace") if isinstance(body, (bytes, bytearray)) else str(body), url),
                    )
                cancel_check = (request.metadata or {}).get("cancel_check")
                lines = response.aiter_lines()
                while True:
                    try:
                        line = await next_stream_line(lines, response, cancel_check)
                    except StreamCancelled:
                        content = "".join(content_parts)
                        reasoning = "".join(reasoning_parts) or None
                        meta: Dict[str, Any] = {"cancelled": True}
                        if reasoning:
                            meta["reasoning"] = reasoning
                        return ModelResponse(
                            messages=[
                                Message(
                                    role=MessageRole.ASSISTANT,
                                    content=content,
                                    metadata=meta if reasoning else None,
                                )
                            ],
                            finish_reason="cancelled",
                            metadata=meta,
                        )
                    except StopAsyncIteration:
                        break
                    line = (line or "").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data_text = line[5:].strip()
                    if data_text == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    response_id = chunk.get("id") or response_id
                    model_name = chunk.get("model") or model_name
                    if isinstance(chunk.get("usage"), dict):
                        usage_raw = chunk["usage"]
                    for choice in chunk.get("choices") or []:
                        finish_reason = choice.get("finish_reason") or finish_reason
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            content_parts.append(delta["content"])
                            gen_tokens += max(1, len(delta["content"]) // 4)
                            if first_token_at is None:
                                first_token_at = _time.monotonic()
                            cb = (request.metadata or {}).get("on_stream_delta")
                            if callable(cb):
                                try:
                                    cb({"type": "content", "text": delta["content"]})
                                except Exception:
                                    pass
                        rc = delta.get("reasoning_content") or delta.get("reasoning")
                        if rc:
                            reasoning_parts.append(rc)
                            gen_tokens += max(1, len(rc) // 4)
                            if first_token_at is None:
                                first_token_at = _time.monotonic()
                            cb = (request.metadata or {}).get("on_stream_delta")
                            if callable(cb):
                                try:
                                    cb({"type": "reasoning", "text": rc})
                                except Exception:
                                    pass
                        for tc in delta.get("tool_calls") or []:
                            idx = int(tc.get("index") or 0)
                            slot = tool_acc.setdefault(
                                idx, {"id": "", "name": "", "arguments": ""}
                            )
                            if tc.get("id"):
                                slot["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                slot["name"] += fn["name"]
                            if fn.get("arguments"):
                                slot["arguments"] += fn["arguments"]

        tool_calls: List[ToolCall] = []
        for i, slot in sorted(tool_acc.items()):
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
        content = "".join(content_parts)
        from Kerniq.models.text_tools import adopt_channel_calls

        content, adopted = adopt_channel_calls(content, tool_calls or None)
        tool_calls = list(adopted or [])
        reasoning = "".join(reasoning_parts) or None
        assistant = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls or None,
            metadata={"reasoning": reasoning} if reasoning else None,
        )
        usage = None
        if usage_raw:
            usage = TokenUsage(
                prompt_tokens=usage_raw.get("prompt_tokens"),
                completion_tokens=usage_raw.get("completion_tokens"),
                total_tokens=usage_raw.get("total_tokens"),
            )
        tps = None
        if usage_raw.get("completion_tokens") and first_token_at:
            dt = max(0.001, _time.monotonic() - first_token_at)
            tps = float(usage_raw["completion_tokens"]) / dt
        elif gen_tokens and first_token_at:
            dt = max(0.001, _time.monotonic() - first_token_at)
            tps = float(gen_tokens) / dt
        return ModelResponse(
            messages=[assistant],
            finish_reason=finish_reason or ("tool_calls" if tool_calls else "stop"),
            usage=usage,
            request_id=response_id,
            metadata={
                "api": "openai_compat /v1/chat/completions stream",
                "reasoning": reasoning,
                "model": model_name,
                "tokens_per_second": tps,
            },
        )

