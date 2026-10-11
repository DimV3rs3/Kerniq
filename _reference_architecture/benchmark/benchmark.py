#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LOCAL LM STUDIO AGENT BENCHMARK
================================

Purpose
-------
Autonomous benchmark for local LLMs running through LM Studio.

The benchmark:
    1. Reads model IDs from models.txt
    2. Reads system prompt from system_prompt.txt
    3. Reads task from task.txt
    4. Discovers model metadata from LM Studio
    5. Discovers maximum context length when available
    6. Unloads previously loaded models
    7. Loads the selected model with maximum discovered context
    8. Creates an isolated workspace for that model
    9. Gives the model the same task and tools
   10. Lets the model autonomously:
          - read files
          - create files
          - overwrite files
          - edit files
          - delete files
          - list directories
          - execute PowerShell commands
   11. Captures:
          - wall-clock time
          - TTFT
          - generation speed
          - prompt tokens
          - completion tokens
          - reasoning tokens
          - tool calls
          - commands
          - command duration
          - stdout/stderr sizes
          - file operations
          - iterations
          - idle iterations
          - repeated operations
          - errors
   12. Saves the resulting project and report
   13. Unloads the model
   14. Runs the next model
   15. Builds a complete benchmark report at the end.

No third-party Python packages are required. HTTP transport uses http.client only.

Test environment:
    Windows + PowerShell + LM Studio

LM Studio:
    http://127.0.0.1:1234

IMPORTANT:
    This script deliberately does NOT include a concrete benchmark task.
    Put the task into task.txt.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import shutil
import hashlib
import traceback
import subprocess
import threading
import http.client
import socket
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent

CONFIG_DIR = SCRIPT_DIR / "config"
SYSTEM_PROMPT_FILE = CONFIG_DIR / "system_prompt.txt"
TASK_FILE = CONFIG_DIR / "task.txt"
VERIFICATION_FILE = CONFIG_DIR / "verification.txt"

RESULTS_DIR = SCRIPT_DIR / "benchmark_results"

LM_STUDIO_BASE = "http://127.0.0.1:1234"

API_V1 = LM_STUDIO_BASE + "/api/v1"
API_OPENAI = LM_STUDIO_BASE + "/v1"

# Set this if your LM Studio server requires authentication.
# Leave empty when authentication is disabled.
LM_API_TOKEN = os.environ.get("LM_API_TOKEN", "")

# --------------------------------------------------------------------------
# Benchmark limits
# --------------------------------------------------------------------------

MAX_AGENT_ITERATIONS = 1000
MAX_TOTAL_TOOL_CALLS = 3000

MAX_SINGLE_COMMAND_SECONDS = 300
MAX_TOTAL_RUNTIME_SECONDS = 24 * 60 * 60

# If the model performs the exact same tool operation this many times
# consecutively, the benchmark will terminate it.
MAX_IDENTICAL_CONSECUTIVE_TOOL_CALLS = 20

# A loop is considered real only when the exact same tool+arguments produce
# the same project state and effectively the same result repeatedly.
# This prevents legitimate repeated operations from being killed just because
# their tool signature is identical.
MAX_STAGNANT_IDENTICAL_TOOL_CALLS = 8

# If there is no observable project activity for this many seconds,
# we still allow the model to continue, but record an idle period.
IDLE_WARNING_SECONDS = 120

# --------------------------------------------------------------------------
# Context management
# --------------------------------------------------------------------------

# Cline-like rolling context compaction. The benchmark keeps the native
# tool-calling protocol, but periodically replaces old conversation turns
# with a compact task-state summary so prompt tokens do not grow without
# bound.
ENABLE_CONTEXT_COMPACTION = True
CONTEXT_COMPACTION_TRIGGER_RATIO = 0.75
CONTEXT_COMPACTION_KEEP_RECENT_MESSAGES = 8
CONTEXT_COMPACTION_MAX_SUMMARY_INPUT_CHARS = 60_000
CONTEXT_COMPACTION_MAX_OUTPUT_TOKENS = 4_096
CONTEXT_COMPACTION_MIN_INTERVAL_TURNS = 8

# The model may legitimately spend a long time in one generation. The old
# 360-second-ish request timeout was responsible for several apparent model
# failures. The global benchmark watchdog remains the hard overall limit.
MODEL_REQUEST_TIMEOUT_SECONDS = 4 * 60 * 60
STREAM_MODEL_RESPONSES = True
STREAM_READ_CHUNK_SIZE = 64 * 1024

# A model is allowed to spend many hours in one generation. This is deliberately
# much higher than the 150k-token pathological tool call seen in earlier runs.
# It is a safety fuse, not a normal generation limit. The stream is terminated
# only if the reconstructed response grows beyond this many characters.
MAX_SINGLE_RESPONSE_CHARS = 20_000_000

# Maximum amount of stdout/stderr stored in a single event.
# The complete output is saved separately when possible.
MAX_LOGGED_COMMAND_OUTPUT_CHARS = 100_000

# --------------------------------------------------------------------------
# Model selection
# --------------------------------------------------------------------------

# Explicitly forbidden because of the user's hardware constraints.
EXCLUDED_MODELS: set[str] = set()

# --------------------------------------------------------------------------
# LM Studio load configuration
# --------------------------------------------------------------------------

USE_FLASH_ATTENTION = True

# KV cache on GPU can be expensive on 12 GB VRAM.
# False is deliberately safer for the user's configuration.
OFFLOAD_KV_CACHE_TO_GPU = True

# Let LM Studio choose its normal/default MoE expert count.
# None = do not send num_experts.
NUM_EXPERTS = None

# Let LM Studio choose its normal eval batch size.
# None = do not send eval_batch_size.
EVAL_BATCH_SIZE = None

# --------------------------------------------------------------------------
# Generation configuration
# --------------------------------------------------------------------------

TEMPERATURE = 0.1

# We intentionally don't hard-code a small max_tokens value.
#
# The model's context_length is discovered and supplied during loading.
# The API is then allowed to use the remaining context for generation.
#
# If you want an explicit ceiling later, set this to an integer.
MAX_OUTPUT_TOKENS = None

# --------------------------------------------------------------------------
# PowerShell
# --------------------------------------------------------------------------

POWERSHELL_EXE = "powershell.exe"

# --------------------------------------------------------------------------
# Fresh workspace policy
# --------------------------------------------------------------------------

# True:
#   If a model's previous benchmark folder exists, it is renamed to a
#   timestamped archive and a completely new project is created.
#
# False:
#   Existing workspace is reused.
#
# For an actual benchmark, TRUE is recommended.
FRESH_MODEL_WORKSPACE = True 

# ============================================================================
# GENERAL HELPERS
# ============================================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def monotonic() -> float:
    return time.perf_counter()


def safe_filename(value: str) -> str:
    """
    Convert a model key such as:
        qwen/qwen3.5-9b-coder

    into a Windows-safe directory name.
    """
    value = value.strip()

    value = value.replace("/", "__")
    value = value.replace("\\", "__")

    value = re.sub(r'[<>:"|?*]', "_", value)
    value = re.sub(r"\s+", "_", value)

    if not value:
        value = "unknown_model"

    return value[:180]


def atomic_write_text(path: Path, text: str) -> None:
    """
    Write text atomically where possible.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    temp = path.with_suffix(path.suffix + ".tmp")

    temp.write_text(
        text,
        encoding="utf-8",
        errors="replace",
    )

    try:
        temp.replace(path)
    except Exception:
        shutil.move(str(temp), str(path))


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "a",
        encoding="utf-8",
        errors="replace",
    ) as f:
        f.write(json.dumps(
            obj,
            ensure_ascii=False,
            default=str,
        ))
        f.write("\n")


def count_chars(text: str) -> int:
    return len(text or "")


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8", errors="replace")
    ).hexdigest()


def human_seconds(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/A"

    seconds = max(0.0, seconds)

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if hours:
        return f"{hours}h {minutes}m {secs:.2f}s"

    if minutes:
        return f"{minutes}m {secs:.2f}s"

    return f"{secs:.2f}s"


# ============================================================================
# HTTP CLIENT
# ============================================================================

class LMStudioHTTPError(RuntimeError):
    pass


def quote_url_component(value: str) -> str:
    """Percent-encode one URL path component."""
    safe = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.~-"
    return "".join(chr(byte) if byte in safe else f"%{byte:02X}" for byte in value.encode("utf-8"))


class LMStudioClient:
    def __init__(self, base_url: str = LM_STUDIO_BASE, token: str = "", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Connection": "keep-alive"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _connection(self, timeout: Optional[int] = None):
        match = re.fullmatch(r"(https?)://([^/:]+)(?::(\d+))?", self.base_url)
        if not match:
            raise LMStudioHTTPError(f"Unsupported LM Studio base URL: {self.base_url}")
        scheme, host, port_text = match.groups()
        port = int(port_text) if port_text else (443 if scheme == "https" else 80)
        cls = http.client.HTTPSConnection if scheme == "https" else http.client.HTTPConnection
        return cls(host, port, timeout=timeout or self.timeout)

    @staticmethod
    def _decode_json(raw: bytes) -> dict[str, Any]:
        if not raw:
            return {}
        text = raw.decode("utf-8", errors="replace")
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {"_raw_json": value}
        except json.JSONDecodeError:
            return {"_raw": text}

    RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
    RETRY_ATTEMPTS = 8
    RETRY_BASE_DELAY = 2.0
    RETRY_MAX_DELAY = 15.0

    def request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None,
                timeout: Optional[int] = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        conn = self._connection(timeout)
        url = self.base_url + path
        try:
            conn.request(method.upper(), path, body=body, headers=self._headers())
            response = conn.getresponse()
            raw = response.read()
            if not 200 <= response.status < 300:
                raise LMStudioHTTPError(
                    f"HTTP {response.status} from {method.upper()} {url}: "
                    f"{raw.decode('utf-8', errors='replace')}"
                )
            return self._decode_json(raw)
        except LMStudioHTTPError:
            raise
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            raise LMStudioHTTPError(f"HTTP transport error for {method.upper()} {url}: {exc}") from exc
        finally:
            conn.close()

    def stream_chat_completions(self, payload: dict[str, Any], timeout: Optional[int] = None,
                                on_event: Optional[Any] = None) -> dict[str, Any]:
        """Stream OpenAI-compatible SSE and reconstruct a chat completion."""
        path = "/v1/chat/completions"
        url = self.base_url + path
        stream_payload = dict(payload)
        stream_payload["stream"] = True
        stream_payload["stream_options"] = {"include_usage": True}
        body = json.dumps(stream_payload, ensure_ascii=False).encode("utf-8")
        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        conn = self._connection(timeout)

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_acc: dict[int, dict[str, Any]] = {}
        usage: dict[str, Any] = {}
        finish_reason: Optional[str] = None
        response_id = None
        model_name = None
        started = monotonic()
        first_event_at: Optional[float] = None
        response_chars = 0

        try:
            conn.request("POST", path, body=body, headers=headers)
            response = conn.getresponse()
            if not 200 <= response.status < 300:
                error_body = response.read().decode("utf-8", errors="replace")
                raise LMStudioHTTPError(f"HTTP {response.status} from POST {url}: {error_body}")

            while True:
                raw_line = response.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or line.startswith(":") or not line.startswith("data:"):
                    continue
                data_text = line[5:].strip()
                if data_text == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_text)
                except json.JSONDecodeError:
                    continue

                if first_event_at is None:
                    first_event_at = monotonic()
                if on_event is not None:
                    try:
                        on_event(chunk)
                    except Exception:
                        pass

                response_id = chunk.get("id") or response_id
                model_name = chunk.get("model") or model_name
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0] or {}
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}

                for key in ("content", "text"):
                    value = delta.get(key)
                    if isinstance(value, str) and value:
                        content_parts.append(value)
                        response_chars += len(value)
                for key in ("reasoning_content", "reasoning"):
                    value = delta.get(key)
                    if isinstance(value, str) and value:
                        reasoning_parts.append(value)
                        response_chars += len(value)

                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0))
                    item = tool_acc.setdefault(idx, {
                        "id": "", "type": "function",
                        "function": {"name": "", "arguments": ""},
                    })
                    if tc.get("id"):
                        item["id"] = tc["id"]
                    if tc.get("type"):
                        item["type"] = tc["type"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        item["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        item["function"]["arguments"] += fn["arguments"]
                        response_chars += len(fn["arguments"])

                if response_chars > MAX_SINGLE_RESPONSE_CHARS:
                    raise RuntimeError(
                        "Model response exceeded MAX_SINGLE_RESPONSE_CHARS "
                        f"({MAX_SINGLE_RESPONSE_CHARS:,}). Generation was terminated by the benchmark safety fuse."
                    )
        except LMStudioHTTPError:
            raise
        except (OSError, socket.timeout, http.client.HTTPException) as exc:
            raise LMStudioHTTPError(f"HTTP transport error for POST {url}: {exc}") from exc
        finally:
            conn.close()

        tool_calls = [tool_acc[k] for k in sorted(tool_acc)]
        message: dict[str, Any] = {"role": "assistant", "content": "".join(content_parts)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        if reasoning_parts:
            message["_reasoning_content"] = "".join(reasoning_parts)
        total_elapsed = monotonic() - started
        stats = {"time_to_first_token_seconds": first_event_at - started if first_event_at is not None else None}
        if usage:
            stats.update({
                "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
                "total_output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
            })
        return {
            "id": response_id, "object": "chat.completion", "model": model_name,
            "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            "usage": usage, "stats": stats, "_stream_elapsed_seconds": total_elapsed,
        }

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any], timeout: Optional[int] = None) -> dict[str, Any]:
        return self.request("POST", path, payload, timeout=timeout)


# ============================================================================
class ConsoleProgress:
    """One persistent, in-place progress line for the current model."""

    def __init__(self, model_name: str = "", total: Optional[float] = None):
        self.model_name = model_name
        self.total = total
        self.started = monotonic()
        self.stage_started = self.started
        self.stage = "Подготовка"
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self._last_render_len = 0

    def set_stage(self, stage: str, total: Optional[float] = None) -> None:
        with self.lock:
            if self.stage != stage:
                self.stage = stage
                self.stage_started = monotonic()

            if total is not None:
                self.total = total

    def _render(self) -> None:
        now = monotonic()
        stage_elapsed = now - self.stage_started
        total_elapsed = now - self.started

        # Indeterminate, but visibly moving. A percentage here would be fake:
        # generation length is unknown until the model finishes.
        width = 24
        pos = int(total_elapsed * 5) % (width * 2 - 2)
        if pos >= width:
            pos = (width * 2 - 2) - pos
        left = max(0, pos)
        filled = min(width, max(pos + 1, 1))
        bar = "█" * filled + "░" * (width - filled)
        if left > 0:
            # Shift the apparent activity without changing the fixed width.
            bar = "░" * min(left, width - 1) + "█" + "░" * max(0, width - left - 1)

        with self.lock:
            label = self.stage
            model = self.model_name
            line = (
                f"\r[{bar}] --.-% | {label}: {model} | "
                f"{human_seconds(stage_elapsed)} | "
                f"{human_seconds(total_elapsed)}"
            )
            print(line.ljust(max(120, self._last_render_len)), end="", flush=True)
            self._last_render_len = len(line)

    def _loop(self) -> None:
        while self.running:
            self._render()
            time.sleep(0.20)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.started = monotonic()
        self.stage_started = self.started
        self.thread = threading.Thread(target=self._loop, name="benchmark-progress", daemon=True)
        self.thread.start()

    def stop(self, final_label: Optional[str] = None) -> None:
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=1.0)
        elapsed = monotonic() - self.started
        label = final_label or self.stage
        width = 24
        line = f"\r[{('█' * width)}] 100.0% | {label} | {human_seconds(elapsed)}"
        print(line.ljust(max(120, self._last_render_len)))


def run_with_progress(label: str, func: Any, *args: Any, total: Optional[float] = None, **kwargs: Any) -> Any:
    # Kept for model-management operations outside the agent. The autonomous
    # agent itself uses one persistent progress object for its entire lifetime.
    progress = ConsoleProgress()
    progress.set_stage(label, total)
    progress.start()
    try:
        return func(*args, **kwargs)
    finally:
        progress.stop()


# ============================================================================
# MODEL DISCOVERY
# ============================================================================

def recursive_find_numbers(
    obj: Any,
    wanted_keys: set[str],
    prefix: str = "",
) -> list[tuple[str, float]]:
    """
    Search arbitrary LM Studio JSON recursively for keys such as:
        max_context_length
        context_length
        max_context
    """
    results: list[tuple[str, float]] = []

    if isinstance(obj, dict):

        for key, value in obj.items():

            key_lower = str(key).lower()

            if key_lower in wanted_keys:
                if isinstance(value, (int, float)):
                    results.append(
                        (prefix + key, float(value))
                    )

            results.extend(
                recursive_find_numbers(
                    value,
                    wanted_keys,
                    prefix + str(key) + ".",
                )
            )

    elif isinstance(obj, list):

        for index, item in enumerate(obj):

            results.extend(
                recursive_find_numbers(
                    item,
                    wanted_keys,
                    prefix + f"[{index}].",
                )
            )

    return results


def discover_models(
    client: LMStudioClient,
) -> list[dict[str, Any]]:

    last_error: Optional[Exception] = None

    for attempt in range(1, 9):
        try:
            response = client.get("/api/v1/models")

            models = response.get("models", [])

            if not isinstance(models, list):
                raise RuntimeError(
                    "LM Studio returned an unexpected /api/v1/models response."
                )

            return models

        except LMStudioHTTPError as e:
            last_error = e

            error_text = str(e)

            retryable = (
                any(f"HTTP {code} " in error_text for code in LMStudioClient.RETRYABLE_HTTP_CODES)
                or "HTTP transport error" in error_text
            )

            if not retryable or attempt >= 8:
                raise

            delay = min(
                LMStudioClient.RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                LMStudioClient.RETRY_MAX_DELAY,
            )

            print(
                f"[LM Studio] Временная ошибка подключения "
                f"(попытка {attempt}/8): {error_text}"
            )
            print(
                f"[LM Studio] Повтор через {delay:.1f} сек..."
            )

            time.sleep(delay)


            delay = min(
                LMStudioClient.RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                LMStudioClient.RETRY_MAX_DELAY,
            )

            print(
                f"[LM Studio] Сервер пока недоступен "
                f"(попытка {attempt}/8): {e}"
            )
            print(
                f"[LM Studio] Повтор через {delay:.1f} сек..."
            )

            time.sleep(delay)

    raise RuntimeError(
        f"Could not discover LM Studio models: {last_error}"
    )


def find_model(
    models: list[dict[str, Any]],
    requested_key: str,
) -> Optional[dict[str, Any]]:

    requested = requested_key.strip().lower()

    for model in models:

        key = str(model.get("key", "")).strip()

        if key.lower() == requested:
            return model

    # Fallback: sometimes a user may specify a display name.
    for model in models:

        display_name = str(
            model.get("display_name", "")
        ).strip()

        if display_name.lower() == requested:
            return model

    return None


def discover_max_context(
    client: LMStudioClient,
    model: dict[str, Any],
) -> tuple[Optional[int], str, dict[str, Any]]:

    """
    Attempts to discover the model's actual maximum context.

    Priority:
        1. /api/v1/models response
        2. model's loaded_instances metadata
        3. legacy /api/v0/models/<model>
        4. recursive search for likely keys

    Returns:
        (max_context, source, raw_metadata)
    """

    candidates = []

    # ------------------------------------------------------------------
    # v1 model metadata
    # ------------------------------------------------------------------

    candidates.extend(
        recursive_find_numbers(
            model,
            {
                "max_context_length",
                "max_context",
                "context_length",
                "context_length_max",
                "max_sequence_length",
                "n_ctx_train",
            },
        )
    )

    if candidates:

        # Prefer explicit max fields over generic context_length.
        preferred = [
            item for item in candidates
            if any(
                marker in item[0].lower()
                for marker in (
                    "max_context",
                    "context_length_max",
                    "max_sequence_length",
                    "n_ctx_train",
                )
            )
        ]

        if preferred:
            value = max(
                int(x[1])
                for x in preferred
            )

            return value, "v1 metadata", model

        value = max(
            int(x[1])
            for x in candidates
        )

        return value, "v1 metadata", model

    # ------------------------------------------------------------------
    # Legacy v0 model endpoint.
    #
    # This is only used as a metadata fallback.
    # ------------------------------------------------------------------

    key = str(model.get("key", "")).strip()

    if key:

        encoded_key = quote_url_component(key)

        try:

            legacy = client.get(
                f"/api/v0/models/{encoded_key}"
            )

            candidates = recursive_find_numbers(
                legacy,
                {
                    "max_context_length",
                    "max_context",
                    "context_length",
                    "context_length_max",
                    "n_ctx_train",
                },
            )

            if candidates:

                preferred = [
                    item for item in candidates
                    if any(
                        marker in item[0].lower()
                        for marker in (
                            "max_context",
                            "context_length_max",
                            "max_sequence_length",
                            "n_ctx_train",
                        )
                    )
                ]

                selected = preferred or candidates

                value = max(
                    int(x[1])
                    for x in selected
                )

                return value, "v0 metadata fallback", legacy

        except Exception:
            pass

    return None, "not discovered", model


def discover_native_tool_support(
    client: LMStudioClient,
    model: dict[str, Any],
) -> tuple[bool, str, Any]:
    capabilities = model.get("capabilities")

    if isinstance(capabilities, dict):
        trained = capabilities.get("trained_for_tool_use")
        if trained is True:
            return True, "v1 capabilities.trained_for_tool_use", capabilities
        if trained is False:
            return False, "v1 capabilities.trained_for_tool_use=false", capabilities

    if isinstance(capabilities, list):
        normalized = {
            str(item).strip().lower()
            for item in capabilities
        }
        if "tool_use" in normalized or "tools" in normalized:
            return True, "v1 capabilities list", capabilities
        if capabilities:
            return False, "v1 capabilities list", capabilities

    key = str(model.get("key", "")).strip()
    if key:
        encoded_key = quote_url_component(key)
        try:
            legacy = client.get(f"/api/v0/models/{encoded_key}")
            legacy_caps = legacy.get("capabilities")
            if isinstance(legacy_caps, list):
                normalized = {
                    str(item).strip().lower()
                    for item in legacy_caps
                }
                if "tool_use" in normalized or "tools" in normalized:
                    return True, "v0 capabilities.tool_use", legacy_caps
                return False, "v0 capabilities", legacy_caps
            if isinstance(legacy_caps, dict):
                trained = legacy_caps.get("trained_for_tool_use")
                if trained is True:
                    return True, "v0 capabilities.trained_for_tool_use", legacy_caps
                if trained is False:
                    return False, "v0 capabilities.trained_for_tool_use=false", legacy_caps
        except Exception as e:
            return False, f"capability lookup failed: {e}", None

    return False, "native tool capability not declared", capabilities


# ============================================================================
# MODEL LOAD / UNLOAD
# ============================================================================

def unload_all_models(
    client: LMStudioClient,
) -> list[dict[str, Any]]:

    unloaded = []

    try:
        response = client.get("/api/v1/models")
    except Exception:
        return unloaded

    models = response.get("models", [])

    for model in models:

        instances = model.get(
            "loaded_instances",
            [],
        )

        if not isinstance(instances, list):
            continue

        for instance in instances:

            if isinstance(instance, dict):

                instance_id = (
                    instance.get("instance_id")
                    or instance.get("id")
                    or model.get("key")
                )

            else:
                instance_id = str(instance)

            if not instance_id:
                continue

            try:

                result = client.post(
                    "/api/v1/models/unload",
                    {
                        "instance_id": instance_id,
                    },
                )

                unloaded.append({
                    "instance_id": instance_id,
                    "result": result,
                })

            except Exception as e:

                unloaded.append({
                    "instance_id": instance_id,
                    "error": str(e),
                })

    # Give LM Studio a moment to release memory.
    time.sleep(1.0)

    return unloaded


def load_model(
    client: LMStudioClient,
    model_key: str,
    context_length: Optional[int],
) -> dict[str, Any]:

    payload: dict[str, Any] = {
        "model": model_key,
        "flash_attention": USE_FLASH_ATTENTION,
        "offload_kv_cache_to_gpu": OFFLOAD_KV_CACHE_TO_GPU,
        "echo_load_config": True,
    }

    if context_length is not None:
        payload["context_length"] = context_length

    if NUM_EXPERTS is not None:
        payload["num_experts"] = NUM_EXPERTS

    if EVAL_BATCH_SIZE is not None:
        payload["eval_batch_size"] = EVAL_BATCH_SIZE

    return client.post(
        "/api/v1/models/load",
        payload,
        timeout=600,
    )


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a UTF-8 text file from the current benchmark project. "
                "The path must be relative to the project root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Relative file path inside the project."
                        ),
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": (
                "Create a new UTF-8 text file. "
                "Fails if the file already exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "content": {
                        "type": "string",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or completely overwrite a UTF-8 text file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "content": {
                        "type": "string",
                    },
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace an exact text fragment inside a file. "
                "The operation fails if old_text occurs zero or more than "
                "one time. This prevents accidental broad modifications."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "old_text": {
                        "type": "string",
                    },
                    "new_text": {
                        "type": "string",
                    },
                },
                "required": [
                    "path",
                    "old_text",
                    "new_text",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": (
                "Delete a file from the project."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": (
                "List files and directories. "
                "The path is relative to the project root. "
                "Use an empty string for the project root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                    "recursive": {
                        "type": "boolean",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "file_exists",
            "description": (
                "Check whether a file or directory exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "run_powershell",
            "description": (
                "Execute a PowerShell command in the current project's "
                "root directory. The command runs without a visible "
                "terminal window. stdout, stderr, exit code and duration "
                "are returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 300,
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
        {
        "type": "function",
        "function": {
            "name": "project_snapshot",
            "description": (
                "One-shot quickstart scan of the entire project workspace. "
                "Recursively lists ALL files and directories (equivalent to a "
                "PowerShell Get-ChildItem -Recurse inventory), then reads the "
                "full UTF-8 content of source/config/docs files: .py, .toml, "
                ".md, .txt. Skips __pycache__, *.pyc, .benchmark and other "
                "binary/cache noise. Returns paths + content so the agent can "
                "understand the current project state in a single call. "
                "Prefer this tool as the FIRST action at the start of a task."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Relative directory to scan. Use empty string \"\" "
                            "for the project root."
                        ),
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": (
                            "If true (default), also return full text of "
                            ".py/.toml/.md/.txt files. If false, only the "
                            "recursive file/directory listing is returned."
                        ),
                    },
                    "max_file_chars": {
                        "type": "integer",
                        "minimum": 1000,
                        "maximum": 500000,
                        "description": (
                            "Per-file content cap. Larger files are truncated "
                            "with a marker. Default 200000."
                        ),
                    },
                    "max_total_chars": {
                        "type": "integer",
                        "minimum": 10000,
                        "maximum": 2000000,
                        "description": (
                            "Hard budget for all file contents combined. "
                            "Default 800000. Remaining files are listed only."
                        ),
                    },
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional override of extensions to read "
                            "(without leading dot). Default: py, toml, md, txt."
                        ),
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
]


# ============================================================================
# PROJECT PATH SECURITY
# ============================================================================

class ProjectPathError(RuntimeError):
    pass


def resolve_project_path(
    project_root: Path,
    relative_path: str,
) -> Path:

    if not isinstance(relative_path, str):
        raise ProjectPathError(
            "Path must be a string."
        )

    relative_path = relative_path.strip()

    if not relative_path:
        return project_root

    candidate = Path(relative_path)

    if candidate.is_absolute():
        raise ProjectPathError(
            "Absolute paths are not allowed."
        )

    resolved = (
        project_root / candidate
    ).resolve()

    root_resolved = project_root.resolve()

    try:
        resolved.relative_to(root_resolved)
    except ValueError as e:
        raise ProjectPathError(
            "Path escapes the benchmark project root."
        ) from e

    return resolved


# ============================================================================
# COMMAND RUNNER
# ============================================================================

class CommandResult:
    def __init__(
        self,
        command: str,
        cwd: Path,
        timeout_seconds: int,
    ):
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds

        self.started_at = utc_now_iso()
        self.started_monotonic = monotonic()

        self.finished_at: Optional[str] = None
        self.duration_seconds: Optional[float] = None

        self.exit_code: Optional[int] = None
        self.stdout = ""
        self.stderr = ""

        self.timed_out = False
        self.exception: Optional[str] = None

    def finish(self) -> None:

        self.finished_at = utc_now_iso()

        self.duration_seconds = (
            monotonic() - self.started_monotonic
        )


def run_hidden_powershell(
    project_root: Path,
    command: str,
    timeout_seconds: int,
) -> CommandResult:

    timeout_seconds = max(
        1,
        min(
            int(timeout_seconds),
            MAX_SINGLE_COMMAND_SECONDS,
        ),
    )

    result = CommandResult(
        command,
        project_root,
        timeout_seconds,
    )

    # ------------------------------------------------------------------
    # PowerShell is launched with cwd = current model's project root.
    # CREATE_NO_WINDOW means there is no visible console window.
    # ------------------------------------------------------------------

    creationflags = getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )

    startupinfo = None

    if os.name == "nt":

        startupinfo = subprocess.STARTUPINFO()

        startupinfo.dwFlags |= (
            subprocess.STARTF_USESHOWWINDOW
        )

        startupinfo.wShowWindow = 0

    try:

        process = subprocess.Popen(
            [
                POWERSHELL_EXE,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            cwd=str(project_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            startupinfo=startupinfo,
        )

        try:

            stdout, stderr = process.communicate(
                timeout=timeout_seconds
            )

            result.exit_code = process.returncode
            result.stdout = stdout or ""
            result.stderr = stderr or ""

        except subprocess.TimeoutExpired:

            result.timed_out = True

            try:
                process.kill()
            except Exception:
                pass

            stdout, stderr = process.communicate()

            result.exit_code = process.returncode

            result.stdout = stdout or ""
            result.stderr = stderr or ""

            result.stderr += (
                "\n[benchmark] COMMAND TIMEOUT\n"
            )

    except Exception as e:

        result.exception = (
            f"{type(e).__name__}: {e}"
        )

    result.finish()

    return result


# ============================================================================
# FILE TOOL IMPLEMENTATION
# ============================================================================

class ToolExecutor:

    def __init__(
        self,
        project_root: Path,
        event_log: Path,
    ):
        self.project_root = project_root.resolve()
        self.event_log = event_log

        self.file_operations = 0
        self.command_operations = 0

    def log(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> None:

        append_jsonl(
            self.event_log,
            {
                "timestamp": utc_now_iso(),
                "event": event_type,
                **data,
            },
        )

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def read_file(
        self,
        path: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            if not target.exists():
                raise FileNotFoundError(
                    f"File does not exist: {path}"
                )

            if not target.is_file():
                raise IsADirectoryError(
                    f"Path is not a file: {path}"
                )

            content = target.read_text(
                encoding="utf-8",
                errors="replace",
            )

            result = {
                "success": True,
                "path": path,
                "chars": len(content),
                "bytes": target.stat().st_size,
                "sha256": sha256_text(content),
                "content": content,
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.file_operations += 1

            self.log(
                "file_read",
                result.copy(),
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_read_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def create_file(
        self,
        path: str,
        content: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            if target.exists():
                raise FileExistsError(
                    f"File already exists: {path}"
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            target.write_text(
                content,
                encoding="utf-8",
            )

            result = {
                "success": True,
                "path": path,
                "chars_written": len(content),
                "bytes_written": target.stat().st_size,
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.file_operations += 1

            self.log(
                "file_created",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_create_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def write_file(
        self,
        path: str,
        content: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            existed_before = target.exists()

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            target.write_text(
                content,
                encoding="utf-8",
            )

            result = {
                "success": True,
                "path": path,
                "created": not existed_before,
                "overwritten": existed_before,
                "chars_written": len(content),
                "bytes_written": target.stat().st_size,
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.file_operations += 1

            self.log(
                "file_written",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_write_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # EDIT
    # ------------------------------------------------------------------

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            if not target.exists():
                raise FileNotFoundError(
                    f"File does not exist: {path}"
                )

            content = target.read_text(
                encoding="utf-8",
                errors="replace",
            )

            occurrences = content.count(
                old_text
            )

            if occurrences == 0:

                raise ValueError(
                    "old_text was not found."
                )

            if occurrences > 1:

                raise ValueError(
                    f"old_text occurs {occurrences} times. "
                    "The edit was rejected because it is ambiguous."
                )

            new_content = content.replace(
                old_text,
                new_text,
                1,
            )

            target.write_text(
                new_content,
                encoding="utf-8",
            )

            result = {
                "success": True,
                "path": path,
                "old_chars": len(old_text),
                "new_chars": len(new_text),
                "chars_before": len(content),
                "chars_after": len(new_content),
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.file_operations += 1

            self.log(
                "file_edited",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_edit_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def delete_file(
        self,
        path: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            if not target.exists():
                raise FileNotFoundError(
                    f"Path does not exist: {path}"
                )

            if not target.is_file():
                raise IsADirectoryError(
                    "delete_file only deletes files."
                )

            size = target.stat().st_size

            target.unlink()

            result = {
                "success": True,
                "path": path,
                "deleted_bytes": size,
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.file_operations += 1

            self.log(
                "file_deleted",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_delete_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------

    def list_directory(
        self,
        path: str,
        recursive: bool = False,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            if not target.exists():
                raise FileNotFoundError(
                    f"Directory does not exist: {path}"
                )

            if not target.is_dir():
                raise NotADirectoryError(
                    f"Not a directory: {path}"
                )

            entries = []

            iterator = (
                target.rglob("*")
                if recursive
                else target.iterdir()
            )

            for item in iterator:

                try:
                    relative = item.relative_to(
                        self.project_root
                    )

                    entries.append({
                        "path": str(relative),
                        "type": (
                            "directory"
                            if item.is_dir()
                            else "file"
                        ),
                        "size": (
                            item.stat().st_size
                            if item.is_file()
                            else None
                        ),
                    })

                except Exception:
                    pass

            entries.sort(
                key=lambda x: (
                    x["type"],
                    x["path"].lower(),
                )
            )

            result = {
                "success": True,
                "path": path,
                "recursive": recursive,
                "count": len(entries),
                "entries": entries,
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "directory_listed",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "directory_list_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # EXISTS
    # ------------------------------------------------------------------

    def file_exists(
        self,
        path: str,
    ) -> dict[str, Any]:

        started = monotonic()

        try:

            target = resolve_project_path(
                self.project_root,
                path,
            )

            result = {
                "success": True,
                "path": path,
                "exists": target.exists(),
                "is_file": target.is_file(),
                "is_directory": target.is_dir(),
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_exists",
                result,
            )

            return result

        except Exception as e:

            result = {
                "success": False,
                "path": path,
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": (
                    monotonic() - started
                ),
            }

            self.log(
                "file_exists_error",
                result,
            )

            return result

    # ------------------------------------------------------------------
    # POWERSHELL
    # ------------------------------------------------------------------

    def run_powershell(
        self,
        command: str,
        timeout_seconds: int = MAX_SINGLE_COMMAND_SECONDS,
    ) -> dict[str, Any]:

        result = run_hidden_powershell(
            self.project_root,
            command,
            timeout_seconds,
        )

        self.command_operations += 1

        stdout_full = result.stdout
        stderr_full = result.stderr

        stdout_logged = stdout_full[
            :MAX_LOGGED_COMMAND_OUTPUT_CHARS
        ]

        stderr_logged = stderr_full[
            :MAX_LOGGED_COMMAND_OUTPUT_CHARS
        ]

        output_dir = (
            self.project_root
            / ".benchmark"
            / "command_outputs"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_id = (
            datetime.now().strftime(
                "%Y%m%d_%H%M%S_%f"
            )
        )

        stdout_file = (
            output_dir
            / f"{output_id}_stdout.txt"
        )

        stderr_file = (
            output_dir
            / f"{output_id}_stderr.txt"
        )

        try:
            stdout_file.write_text(
                stdout_full,
                encoding="utf-8",
                errors="replace",
            )

            stderr_file.write_text(
                stderr_full,
                encoding="utf-8",
                errors="replace",
            )

        except Exception:
            pass

        payload = {
            "success": (
                result.exception is None
                and not result.timed_out
                and result.exit_code == 0
            ),
            "command": command,
            "cwd": str(self.project_root),
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "duration_seconds": result.duration_seconds,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "exception": result.exception,

            "stdout_chars": len(stdout_full),
            "stderr_chars": len(stderr_full),

            "stdout": stdout_logged,
            "stderr": stderr_logged,

            "stdout_file": str(
                stdout_file.relative_to(
                    self.project_root
                )
            ),
            "stderr_file": str(
                stderr_file.relative_to(
                    self.project_root
                ),
            ),
        }

        self.log(
            "powershell",
            payload,
        )

        return payload

    # ------------------------------------------------------------------
    # PROJECT SNAPSHOT (quickstart: list + read sources)
    # ------------------------------------------------------------------

    def project_snapshot(
        self,
        path: str = "",
        include_content: bool = True,
        max_file_chars: int = 200_000,
        max_total_chars: int = 800_000,
        extensions: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Recursive inventory of the project + optional full-text dump of
        source/config/docs files (.py / .toml / .md / .txt by default).

        Combines what the agent would otherwise do with list_directory(recursive)
        + many read_file calls + a PowerShell Get-ChildItem -Recurse.
        """
        started = monotonic()

        SKIP_DIR_NAMES = {
            "__pycache__",
            ".benchmark",
            ".git",
            ".hg",
            ".svn",
            ".mypy_cache",
            ".ruff_cache",
            ".pytest_cache",
            ".tox",
            ".venv",
            "venv",
            "node_modules",
            "dist",
            "build",
            ".idea",
            ".vscode",
        }
        SKIP_FILE_SUFFIXES = {".pyc", ".pyo", ".pyd"}
        DEFAULT_EXTS = {"py", "toml", "md", "txt"}

        try:
            max_file_chars = max(1_000, min(int(max_file_chars), 500_000))
            max_total_chars = max(10_000, min(int(max_total_chars), 2_000_000))

            if extensions is None:
                read_exts = set(DEFAULT_EXTS)
            else:
                read_exts = {
                    str(e).lower().lstrip(".")
                    for e in extensions
                    if isinstance(e, str) and e.strip()
                }
                if not read_exts:
                    read_exts = set(DEFAULT_EXTS)

            target = resolve_project_path(self.project_root, path or "")

            if not target.exists():
                raise FileNotFoundError(f"Path does not exist: {path or '.'}")
            if not target.is_dir():
                raise NotADirectoryError(f"Not a directory: {path or '.'}")

            entries: list[dict[str, Any]] = []
            files_to_read: list[Path] = []

            # Manual walk so we can prune noise directories early.
            for root, dirnames, filenames in os.walk(target, topdown=True, followlinks=False):
                root_path = Path(root)

                # Prune skipped directory names in-place.
                dirnames[:] = [
                    d for d in dirnames
                    if d not in SKIP_DIR_NAMES and not d.startswith(".")
                ]

                try:
                    rel_root = root_path.relative_to(self.project_root)
                except ValueError:
                    continue

                # Directory entry (skip the start root itself if path was empty).
                if root_path != target or (path and path.strip()):
                    entries.append({
                        "path": str(rel_root).replace("\\", "/"),
                        "type": "directory",
                        "size": None,
                    })

                for name in sorted(filenames):
                    file_path = root_path / name
                    suffix = file_path.suffix.lower()

                    if suffix in SKIP_FILE_SUFFIXES:
                        continue
                    if name.startswith(".") and name not in {".gitignore", ".env.example"}:
                        # Keep common project meta; skip other hidden junk.
                        if name not in {".gitignore"}:
                            continue

                    try:
                        rel = file_path.relative_to(self.project_root)
                        rel_s = str(rel).replace("\\", "/")
                        size = file_path.stat().st_size
                    except OSError:
                        continue

                    entries.append({
                        "path": rel_s,
                        "type": "file",
                        "size": size,
                    })

                    ext = suffix.lstrip(".")
                    if include_content and ext in read_exts:
                        files_to_read.append(file_path)

            entries.sort(key=lambda x: (x["type"], x["path"].lower()))

            contents: list[dict[str, Any]] = []
            total_chars = 0
            truncated_budget = False
            read_errors: list[dict[str, str]] = []

            if include_content:
                for file_path in sorted(files_to_read, key=lambda p: str(p).lower()):
                    try:
                        rel_s = str(
                            file_path.relative_to(self.project_root)
                        ).replace("\\", "/")
                    except ValueError:
                        continue

                    if total_chars >= max_total_chars:
                        truncated_budget = True
                        contents.append({
                            "path": rel_s,
                            "skipped": True,
                            "reason": "max_total_chars budget exhausted",
                        })
                        continue

                    try:
                        text = file_path.read_text(encoding="utf-8", errors="replace")
                    except OSError as e:
                        read_errors.append({
                            "path": rel_s,
                            "error": f"{type(e).__name__}: {e}",
                        })
                        continue

                    file_truncated = False
                    if len(text) > max_file_chars:
                        text = (
                            text[:max_file_chars]
                            + f"\n\n...[TRUNCATED BY project_snapshot: "
                              f"file longer than {max_file_chars} chars]...\n"
                        )
                        file_truncated = True

                    remaining = max_total_chars - total_chars
                    if len(text) > remaining:
                        text = (
                            text[:remaining]
                            + "\n\n...[TRUNCATED BY project_snapshot: "
                              "max_total_chars budget]...\n"
                        )
                        file_truncated = True
                        truncated_budget = True

                    total_chars += len(text)
                    contents.append({
                        "path": rel_s,
                        "chars": len(text),
                        "truncated": file_truncated,
                        "content": text,
                    })

            result = {
                "success": True,
                "path": path or "",
                "recursive": True,
                "include_content": include_content,
                "extensions": sorted(read_exts),
                "entry_count": len(entries),
                "file_count": sum(1 for e in entries if e["type"] == "file"),
                "directory_count": sum(1 for e in entries if e["type"] == "directory"),
                "entries": entries,
                "content_file_count": len([c for c in contents if not c.get("skipped")]),
                "content_total_chars": total_chars,
                "content_budget_exhausted": truncated_budget,
                "contents": contents,
                "read_errors": read_errors,
                "duration_seconds": monotonic() - started,
            }

            self.file_operations += 1
            self.log("project_snapshot", {
                "path": result["path"],
                "entry_count": result["entry_count"],
                "content_file_count": result["content_file_count"],
                "content_total_chars": result["content_total_chars"],
                "duration_seconds": result["duration_seconds"],
            })
            return result

        except Exception as e:
            result = {
                "success": False,
                "path": path or "",
                "error": f"{type(e).__name__}: {e}",
                "duration_seconds": monotonic() - started,
            }
            self.log("project_snapshot_error", result)
            return result

    # ------------------------------------------------------------------
    # DISPATCH
    # ------------------------------------------------------------------

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:

        if name == "read_file":
            return self.read_file(
                arguments["path"]
            )

        if name == "create_file":
            return self.create_file(
                arguments["path"],
                arguments["content"],
            )

        if name == "write_file":
            return self.write_file(
                arguments["path"],
                arguments["content"],
            )

        if name == "edit_file":
            return self.edit_file(
                arguments["path"],
                arguments["old_text"],
                arguments["new_text"],
            )

        if name == "delete_file":
            return self.delete_file(
                arguments["path"]
            )

        if name == "list_directory":
            return self.list_directory(
                arguments["path"],
                bool(arguments.get("recursive", False)),
            )

        if name == "file_exists":
            return self.file_exists(
                arguments["path"]
            )

        if name == "run_powershell":
            return self.run_powershell(
                arguments["command"],
                int(
                    arguments.get(
                        "timeout_seconds",
                        MAX_SINGLE_COMMAND_SECONDS,
                    )
                ),
            )

        if name == "project_snapshot":
            return self.project_snapshot(
                path=arguments.get("path", ""),
                include_content=bool(arguments.get("include_content", True)),
                max_file_chars=int(arguments.get("max_file_chars", 200_000)),
                max_total_chars=int(arguments.get("max_total_chars", 800_000)),
                extensions=arguments.get("extensions"),
            )

        return {
            "success": False,
            "error": (
                f"Unknown tool: {name}"
            ),
        }


# ============================================================================
# BENCHMARK AGENT
# ============================================================================

def project_state_fingerprint(root: Path) -> str:
    """Cheap fingerprint used to distinguish repeated calls from progress."""
    h = hashlib.sha256()
    try:
        for path in sorted(root.rglob("*"), key=lambda x: x.as_posix().lower()):
            if not path.is_file() or ".benchmark" in path.parts:
                continue
            try:
                st = path.stat()
                rel = path.relative_to(root).as_posix()
                h.update(rel.encode("utf-8", errors="replace"))
                h.update(str(st.st_size).encode())
                h.update(str(st.st_mtime_ns).encode())
            except OSError:
                continue
    except OSError:
        pass
    return h.hexdigest()


def compact_text(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= limit:
        return text
    head = max(0, limit // 2)
    tail = max(0, limit - head)
    return text[:head] + "\n...[TRUNCATED BY BENCHMARK]...\n" + text[-tail:]


class BenchmarkAgent:

    def __init__(
        self,
        client: LMStudioClient,
        model_key: str,
        model_metadata: dict[str, Any],
        context_length: Optional[int],
        system_prompt: str,
        task: str,
        project_root: Path,
        run_dir: Path,
    ):

        self.client = client
        self.model_key = model_key
        self.model_metadata = model_metadata
        self.context_length = context_length

        self.system_prompt = system_prompt
        self.task = task

        self.project_root = project_root
        self.run_dir = run_dir

        self.event_log = (
            run_dir / "events.jsonl"
        )

        self.tool_log = (
            run_dir / "tools.jsonl"
        )

        self.message_log = (
            run_dir / "messages.jsonl"
        )

        self.executor = ToolExecutor(
            project_root,
            self.tool_log,
        )

        self.messages: list[dict[str, Any]] = []

        self.iterations = 0
        self.tool_calls = 0

        self.total_request_time = 0.0

        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_reasoning_tokens = 0

        self.total_output_chars = 0
        self.total_input_chars = 0

        self.ttft_values: list[float] = []
        self.tokens_per_second_values: list[float] = []

        self.failed_tool_calls = 0
        self.successful_tool_calls = 0

        self.idle_periods: list[dict[str, Any]] = []

        self.last_activity = monotonic()
        self.last_tool_signature = None
        self.same_tool_count = 0
        self.stagnant_same_tool_count = 0
        self.last_tool_result_signature: Optional[str] = None
        self.last_project_fingerprint: Optional[str] = None
        self.loop_history: list[dict[str, Any]] = []

        self.last_prompt_tokens = 0
        self.compaction_count = 0
        self.compaction_prompt_tokens = 0
        self.compaction_output_tokens = 0
        self.last_compaction_turn = 0
        self.rolling_summary = ""

        self.started_at = utc_now_iso()
        self.started_monotonic = monotonic()

        self.finished_at: Optional[str] = None

        self.status = "NOT_STARTED"
        self.stop_reason: Optional[str] = None

        self.final_message = ""

        # One persistent UI line for the entire model run. Tool execution and
        # streaming generation only change this line's state.
        self.progress: Optional[ConsoleProgress] = None

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def log_event(
        self,
        event: str,
        data: dict[str, Any],
    ) -> None:

        append_jsonl(
            self.event_log,
            {
                "timestamp": utc_now_iso(),
                "event": event,
                **data,
            },
        )

    def log_message(
        self,
        role: str,
        content: Any,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:

        record = {
            "timestamp": utc_now_iso(),
            "role": role,
            "content": content,
        }

        if extra:
            record.update(extra)

        append_jsonl(
            self.message_log,
            record,
        )

    # ------------------------------------------------------------------
    # Initial prompt
    # ------------------------------------------------------------------

    def build_initial_user_message(self) -> str:

        return f"""
BENCHMARK TASK

You are operating inside an isolated local software project.

Your task is defined below.

---------------- TASK BEGIN ----------------

{self.task}

---------------- TASK END ------------------

You have access to the benchmark tools provided by the host program.

You MUST actually perform the task.

Do not merely describe code that could be written.
Create and modify the project files using the provided tools.

Use PowerShell when execution, compilation, testing, validation,
inspection, or other terminal operations are required.

The project root is the current working directory for PowerShell.

Do not access files outside the project root.

MANDATORY FIRST ACTION
----------------------
Before any other tool calls, planning text, or file writes, you MUST call
the tool `project_snapshot` exactly once with:

  path: ""
  include_content: true

This returns the full recursive file tree and the contents of all .py,
.toml, .md and .txt files in the workspace. Use that result as your
single source of truth about the current project state. Do not call
list_directory or many individual read_file calls for the initial audit
when project_snapshot is available.

Only after you have received and used the project_snapshot result may
you proceed with architecture, implementation, tests and documentation.

When you believe the task is completely finished, verify the result
as thoroughly as practical.

At the very end, provide a concise final response beginning with:

TASK_COMPLETE

if and only if you consider the task successfully completed.

If the task cannot be completed, begin the final response with:

TASK_FAILED

and explain why.

Begin working now by calling project_snapshot.
""".strip()

    # ------------------------------------------------------------------
    # Request to model
    # ------------------------------------------------------------------

    def request_model(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_key,
            "messages": self.messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": TEMPERATURE,
        }
        if MAX_OUTPUT_TOKENS is not None:
            payload["max_tokens"] = MAX_OUTPUT_TOKENS

        started = monotonic()
        if self.progress:
            self.progress.set_stage("Обработка промпта")

        def on_stream_event(chunk: dict[str, Any]) -> None:
            choices = chunk.get("choices") or []
            if not choices:
                return
            delta = choices[0].get("delta") or {}
            has_reasoning = bool(delta.get("reasoning_content") or delta.get("reasoning"))
            has_content = bool(delta.get("content") or delta.get("text"))
            has_tools = bool(delta.get("tool_calls"))
            if self.progress:
                if has_reasoning:
                    self.progress.set_stage("Обдумывание")
                elif has_tools:
                    self.progress.set_stage("Генерация вызова инструмента")
                elif has_content:
                    self.progress.set_stage("Генерация ответа")

        try:
            if STREAM_MODEL_RESPONSES:
                response = self.client.stream_chat_completions(
                    payload,
                    timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
                    on_event=on_stream_event,
                )
            else:
                response = self.client.post(
                    "/v1/chat/completions",
                    payload,
                    timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
                )
        except Exception as e:
            elapsed = monotonic() - started
            self.total_request_time += elapsed
            self.log_event("model_request_error", {
                "duration_seconds": elapsed,
                "error": f"{type(e).__name__}: {e}",
            })
            if self.progress:
                self.progress.set_stage("Ошибка запроса")
            raise

        elapsed = monotonic() - started
        self.total_request_time += elapsed
        self.last_activity = monotonic()

        usage = response.get("usage") or {}
        stats = response.get("stats") or {}
        prompt_tokens = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        completion_tokens = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        if not prompt_tokens:
            prompt_tokens = int(stats.get("input_tokens", 0) or 0)
        if not completion_tokens:
            completion_tokens = int(stats.get("total_output_tokens", 0) or 0)

        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens

        reasoning = usage.get("reasoning_tokens", stats.get("reasoning_output_tokens", 0))
        if isinstance(reasoning, dict):
            reasoning = reasoning.get("count", 0)
        self.total_reasoning_tokens += int(reasoning or 0)

        self.last_prompt_tokens = prompt_tokens
        ttft = stats.get("time_to_first_token_seconds")
        if isinstance(ttft, (int, float)):
            self.ttft_values.append(float(ttft))
        tps = stats.get("tokens_per_second")
        if isinstance(tps, (int, float)):
            self.tokens_per_second_values.append(float(tps))
        elif completion_tokens and elapsed > 0:
            # Streaming /v1/chat/completions does not always return LM Studio's
            # native tokens_per_second field. Derive a conservative wall-clock
            # rate so the benchmark still has a useful speed metric.
            self.tokens_per_second_values.append(completion_tokens / elapsed)

        choice_list = response.get("choices") or []
        if not choice_list:
            raise RuntimeError("LM Studio returned no choices.")
        message = choice_list[0].get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        self.total_output_chars += len(str(content))

        self.log_message("assistant", content, {
            "tool_calls": tool_calls,
            "reasoning_chars": len(message.get("_reasoning_content", "")),
            "raw_response": response,
            "duration_seconds": elapsed,
        })

        clean_message = {
            "role": "assistant",
            "content": content,
        }

        if tool_calls:
            clean_message["tool_calls"] = tool_calls

        return {
            "response": response,
            "message": clean_message,
            "content": content,
            "tool_calls": tool_calls,
            "duration_seconds": elapsed,
        }

    # ------------------------------------------------------------------
    # Context compaction
    # ------------------------------------------------------------------

    def _compact_source(self) -> str:
        """Build a bounded, information-dense source for the compactor."""
        chunks: list[str] = []
        chunks.append("BENCHMARK TASK:\n" + self.task)
        if self.rolling_summary:
            chunks.append("\nPREVIOUS ROLLING SUMMARY:\n" + self.rolling_summary)

        # Preserve the beginning of the conversation (system + initial task)
        # and a bounded tail. Old tool payloads can contain huge source files,
        # so they are aggressively truncated here.
        for index, msg in enumerate(self.messages):
            if index < 2 or index >= max(2, len(self.messages) - 16):
                role = msg.get("role", "?")
                content = msg.get("content", "")
                if role == "system":
                    continue
                chunks.append(
                    f"\n[{role} message {index}]\n{compact_text(content, 3500)}"
                )

        # Tool history is more useful than raw assistant chatter for software
        # engineering. Read it from the already persisted log and keep the most
        # recent records only.
        try:
            if self.tool_log.exists():
                lines = self.tool_log.read_text(encoding="utf-8", errors="replace").splitlines()
                recent = lines[-24:]
                chunks.append("\nRECENT TOOL EVENTS:\n" + "\n".join(compact_text(x, 2200) for x in recent))
        except Exception:
            pass

        snapshot = []
        try:
            for path in sorted(self.project_root.rglob("*"), key=lambda x: x.as_posix().lower()):
                if path.is_file() and ".benchmark" not in path.parts:
                    try:
                        snapshot.append(f"{path.relative_to(self.project_root).as_posix()} ({path.stat().st_size} bytes)")
                    except OSError:
                        pass
        except OSError:
            pass
        chunks.append("\nCURRENT PROJECT FILES:\n" + "\n".join(snapshot[:500]))

        return compact_text("\n".join(chunks), CONTEXT_COMPACTION_MAX_SUMMARY_INPUT_CHARS)

    def should_compact_context(self) -> bool:
        if not ENABLE_CONTEXT_COMPACTION or not self.context_length:
            return False
        if self.compaction_count and self.iterations - self.last_compaction_turn < CONTEXT_COMPACTION_MIN_INTERVAL_TURNS:
            return False
        if self.last_prompt_tokens >= int(self.context_length * CONTEXT_COMPACTION_TRIGGER_RATIO):
            return True
        # Fallback for APIs that omit token usage.
        approx_chars = sum(len(str(m.get("content", ""))) for m in self.messages)
        approx_tokens = approx_chars // 4
        return approx_tokens >= int(self.context_length * CONTEXT_COMPACTION_TRIGGER_RATIO)

    def _get_recent_complete_message_groups(self, max_messages: int) -> list[dict[str, Any]]:
        """
        Return a recent tail of the conversation without breaking tool-call
        message relationships.

        A valid tool-call sequence looks like:

            assistant(tool_calls=[...])
            tool(...)
            tool(...)
            ...

        The assistant message and all immediately following tool results are
        treated as one indivisible group.

        Orphan tool messages are never preserved.
        """
        if max_messages <= 0:
            return []

        groups: list[list[dict[str, Any]]] = []
        i = 0

        while i < len(self.messages):
            msg = self.messages[i]
            role = msg.get("role")

            # An orphan tool message must never survive compaction.
            if role == "tool":
                i += 1
                continue

            # Assistant message containing tool calls starts a complete
            # assistant -> tool-results group.
            if role == "assistant" and msg.get("tool_calls"):
                group = [msg]
                i += 1

                # Consume all immediately following tool results.
                while i < len(self.messages):
                    next_msg = self.messages[i]

                    if next_msg.get("role") != "tool":
                        break

                    group.append(next_msg)
                    i += 1

                groups.append(group)
                continue

            # Normal user/assistant message.
            groups.append([msg])
            i += 1

        # Take complete groups from the end until the requested message
        # budget is reached. Never split a group.
        selected_groups: list[list[dict[str, Any]]] = []
        selected_count = 0

        for group in reversed(groups):
            group_size = len(group)

            # Always preserve at least the newest complete group, even if
            # it is larger than max_messages.
            if selected_groups and selected_count + group_size > max_messages:
                break

            selected_groups.append(group)
            selected_count += group_size

            if selected_count >= max_messages:
                break

        selected_groups.reverse()

        result: list[dict[str, Any]] = []
        for group in selected_groups:
            result.extend(group)

        return result

    def compact_context(self) -> bool:
        """Ask the same model for a durable task-state summary, then roll history."""
        source = self._compact_source()
        prompt = f"""
You are performing context compaction for an autonomous software-engineering agent.
Create a durable, factual state summary that lets the agent continue the SAME task
without seeing the old conversation.

Include:
- original task and acceptance criteria
- files/modules created or changed and their important APIs/decisions
- tests/builds/commands already run and their results
- known failures, bugs, attempted fixes, and unresolved issues
- important data formats, paths, interfaces, constraints, and edge cases
- what remains to be done

Do NOT invent anything. Do not give generic advice. Preserve concrete names and facts.
Keep it concise but information-dense. Return only the summary.

SOURCE:
{source}
""".strip()

        if self.progress:
            self.progress.set_stage("Компактирование контекста")

        self.log_event("context_compaction_started", {
            "turn": self.iterations,
            "trigger_prompt_tokens": self.last_prompt_tokens,
            "context_length": self.context_length,
            "source_chars": len(source),
        })

        payload = {
            "model": self.model_key,
            "messages": [
                {"role": "system", "content": "You are a precise software-project context summarizer."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "max_tokens": CONTEXT_COMPACTION_MAX_OUTPUT_TOKENS,
        }

        started = monotonic()
        response = self.client.post(
            "/v1/chat/completions",
            payload,
            timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
        )
        elapsed = monotonic() - started

        choices = response.get("choices") or []
        if not choices:
            raise RuntimeError("Context compaction returned no choices")
        message = choices[0].get("message", {}) or {}
        summary = str(message.get("content") or "").strip()
        if not summary:
            raise RuntimeError("Context compaction returned an empty summary")

        usage = response.get("usage") or {}
        self.compaction_prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.compaction_output_tokens += int(usage.get("completion_tokens", 0) or 0)
        self.compaction_count += 1
        self.last_compaction_turn = self.iterations
        self.rolling_summary = summary

        # Keep only the durable state plus a small recent tail.
        #
        # IMPORTANT:
        # Do not slice self.messages directly. A raw slice can start in the
        # middle of an assistant -> tool-call -> tool-result sequence and leave
        # orphaned tool messages in the new conversation history.
        recent = self._get_recent_complete_message_groups(
            CONTEXT_COMPACTION_KEEP_RECENT_MESSAGES
        )

        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_initial_user_message()},
            {
                "role": "user",
                "content": (
                    "COMPACTED TASK STATE — authoritative continuation memory.\n\n"
                    + summary
                    + "\n\nContinue from this state. Do not restart completed work."
                ),
            },
        ]

        self.messages.extend(recent)

        self.log_event("context_compaction_completed", {
            "turn": self.iterations,
            "duration_seconds": elapsed,
            "compaction_index": self.compaction_count,
            "summary_chars": len(summary),
            "prompt_tokens": self.compaction_prompt_tokens,
            "output_tokens": self.compaction_output_tokens,
        })
        return True

    # ------------------------------------------------------------------
    # Tool call execution
    # ------------------------------------------------------------------

    def execute_tool_call(
        self,
        tool_call: dict[str, Any],
    ) -> dict[str, Any]:

        self.tool_calls += 1

        function = tool_call.get(
            "function",
            {},
        )

        name = function.get(
            "name",
            "",
        )

        raw_arguments = function.get(
            "arguments",
            "{}",
        )

        if isinstance(
            raw_arguments,
            dict,
        ):
            arguments = raw_arguments
        else:
            try:
                arguments = json.loads(
                    raw_arguments
                )
            except Exception as e:

                self.failed_tool_calls += 1

                return {
                    "success": False,
                    "error": (
                        "Invalid JSON tool arguments: "
                        f"{e}"
                    ),
                }

        signature = (
            name,
            json.dumps(
                arguments,
                sort_keys=True,
                ensure_ascii=False,
            ),
        )

        before_fingerprint = project_state_fingerprint(self.project_root)

        if signature == self.last_tool_signature:
            self.same_tool_count += 1
        else:
            self.last_tool_signature = signature
            self.same_tool_count = 1
            self.stagnant_same_tool_count = 1
            self.last_tool_result_signature = None

        self.last_activity = monotonic()

        self.log_event(
            "tool_call_start",
            {
                "tool": name,
                "arguments": arguments,
                "tool_call_index": self.tool_calls,
                "iteration": self.iterations,
            },
        )

        if self.progress:
            self.progress.set_stage(f"Инструмент {name}")

        try:
            result = self.executor.execute(
                name,
                arguments,
            )
        except Exception as e:
            result = {
                "success": False,
                "error": f"{type(e).__name__}: {e}",
            }

        after_fingerprint = project_state_fingerprint(self.project_root)
        result_signature = sha256_text(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
        project_changed = before_fingerprint != after_fingerprint
        result_changed = result_signature != self.last_tool_result_signature

        if signature == self.last_tool_signature and self.same_tool_count > 1:
            if project_changed or result_changed:
                self.stagnant_same_tool_count = 1
            else:
                self.stagnant_same_tool_count += 1
        self.last_tool_result_signature = result_signature
        self.last_project_fingerprint = after_fingerprint

        self.loop_history.append({
            "iteration": self.iterations,
            "tool": name,
            "same_signature_count": self.same_tool_count,
            "stagnant_same_signature_count": self.stagnant_same_tool_count,
            "project_changed": project_changed,
            "result_changed": result_changed,
        })
        self.loop_history = self.loop_history[-50:]

        if self.stagnant_same_tool_count >= MAX_STAGNANT_IDENTICAL_TOOL_CALLS:
            self.stop_reason = "stagnant_identical_tool_call_loop"
            self.log_event("tool_loop_detected", {
                "tool": name,
                "arguments": arguments,
                "same_signature_count": self.same_tool_count,
                "stagnant_count": self.stagnant_same_tool_count,
                "project_fingerprint": after_fingerprint,
                "result_signature": result_signature,
            })
            result = {
                "success": False,
                "benchmark_termination": True,
                "error": (
                    "The same tool call produced no project/result progress "
                    f"for {self.stagnant_same_tool_count} consecutive attempts."
                ),
                "loop_diagnostics": self.loop_history[-10:],
            }
            self.failed_tool_calls += 1
            self.log_event("tool_call_end", {
                "tool": name, "arguments": arguments, "result": result,
                "tool_call_index": self.tool_calls, "iteration": self.iterations,
            })
            if self.progress:
                self.progress.set_stage(f"Цикл обнаружен: {name}")
            return result

        if self.same_tool_count >= MAX_IDENTICAL_CONSECUTIVE_TOOL_CALLS:
            self.stop_reason = "identical_tool_call_safety_limit"
            result = {
                "success": False,
                "benchmark_termination": True,
                "error": "Identical tool-call safety limit reached.",
                "loop_diagnostics": self.loop_history[-10:],
            }
            self.failed_tool_calls += 1
            self.log_event("tool_call_end", {
                "tool": name, "arguments": arguments, "result": result,
                "tool_call_index": self.tool_calls, "iteration": self.iterations,
            })
            if self.progress:
                self.progress.set_stage(f"Цикл обнаружен: {name}")
            return result

        if result.get("success"):
            self.successful_tool_calls += 1
            if self.progress:
                self.progress.set_stage(f"Инструмент завершён: {name}")
        else:
            self.failed_tool_calls += 1
            if self.progress:
                self.progress.set_stage(f"Инструмент завершён с ошибкой: {name}")

        self.log_event(
            "tool_call_end",
            {
                "tool": name,
                "arguments": arguments,
                "result": result,
                "tool_call_index": self.tool_calls,
                "iteration": self.iterations,
            },
        )

        return result

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, progress: Optional[ConsoleProgress] = None) -> dict[str, Any]:

        self.status = "RUNNING"
        self.progress = progress or ConsoleProgress(self.model_key)
        if not self.progress.running:
            self.progress.start()
        self.progress.set_stage("Запуск агента")

        self.project_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Initial system prompt.
        self.messages.append({
            "role": "system",
            "content": self.system_prompt,
        })

        self.log_message(
            "system",
            self.system_prompt,
        )

        initial_task = (
            self.build_initial_user_message()
        )

        self.messages.append({
            "role": "user",
            "content": initial_task,
        })

        self.log_message(
            "user",
            initial_task,
        )

        self.log_event(
            "benchmark_started",
            {
                "model": self.model_key,
                "context_length": self.context_length,
            },
        )

        try:

            while True:

                self.iterations += 1

                # ------------------------------------------------------
                # Global runtime limit
                # ------------------------------------------------------

                elapsed_total = (
                    monotonic()
                    - self.started_monotonic
                )

                if (
                    elapsed_total
                    >= MAX_TOTAL_RUNTIME_SECONDS
                ):

                    self.status = "TIMEOUT"
                    self.stop_reason = (
                        "maximum_total_runtime"
                    )

                    break

                # ------------------------------------------------------
                # Iteration limit
                # ------------------------------------------------------

                if (
                    self.iterations
                    > MAX_AGENT_ITERATIONS
                ):

                    self.status = "LIMIT_REACHED"
                    self.stop_reason = (
                        "maximum_iterations"
                    )

                    break

                # ------------------------------------------------------
                # Tool call limit
                # ------------------------------------------------------

                if (
                    self.tool_calls
                    >= MAX_TOTAL_TOOL_CALLS
                ):

                    self.status = "LIMIT_REACHED"
                    self.stop_reason = (
                        "maximum_tool_calls"
                    )

                    break

                # ------------------------------------------------------
                # Idle detection
                # ------------------------------------------------------

                idle_for = (
                    monotonic()
                    - self.last_activity
                )

                if idle_for >= IDLE_WARNING_SECONDS:

                    idle_event = {
                        "started_at": utc_now_iso(),
                        "idle_seconds": idle_for,
                        "iteration": self.iterations,
                    }

                    self.idle_periods.append(
                        idle_event
                    )

                    self.log_event(
                        "idle_warning",
                        idle_event,
                    )

                    self.last_activity = monotonic()

                # ------------------------------------------------------
                # Compact context before it becomes expensive/unsafe.
                # ------------------------------------------------------

                if self.should_compact_context():
                    try:
                        self.compact_context()
                    except Exception as e:
                        # Compaction is an optimization, not a reason to kill
                        # an otherwise healthy benchmark. Record the failure and
                        # continue with the existing context if the server still
                        # accepts it.
                        self.log_event("context_compaction_error", {
                            "turn": self.iterations,
                            "error": f"{type(e).__name__}: {e}",
                        })

                # ------------------------------------------------------
                # Ask model
                # ------------------------------------------------------

                result = self.request_model()

                content = (
                    result.get(
                        "content",
                        "",
                    )
                    or ""
                )

                tool_calls = (
                    result.get(
                        "tool_calls",
                        [],
                    )
                    or []
                )

                assistant_message = (
                    result["message"]
                )

                self.messages.append(
                    assistant_message
                )

                # ------------------------------------------------------
                # Check final state
                # ------------------------------------------------------

                normalized = (
                    content
                    .strip()
                    .upper()
                )

                if (
                    normalized.startswith(
                        "TASK_COMPLETE"
                    )
                ):

                    self.status = "SUCCESS"
                    self.stop_reason = (
                        "model_declared_task_complete"
                    )

                    self.final_message = content

                    break

                if (
                    normalized.startswith(
                        "TASK_FAILED"
                    )
                ):

                    self.status = "FAILED"
                    self.stop_reason = (
                        "model_declared_task_failed"
                    )

                    self.final_message = content

                    break

                # ------------------------------------------------------
                # No tools and no final marker.
                #
                # The model may have returned an ordinary message.
                # Give it an explicit opportunity to continue.
                # ------------------------------------------------------

                if not tool_calls:

                    self.messages.append({
                        "role": "user",
                        "content": (
                            "Continue working on the task. "
                            "Do not stop merely to describe what "
                            "you would do. Use the available tools "
                            "and verify the implementation. "
                            "When truly finished, respond with "
                            "TASK_COMPLETE."
                        ),
                    })

                    self.log_message(
                        "user",
                        (
                            "Continue working on the task. "
                            "Do not stop merely to describe what "
                            "you would do. Use the available tools "
                            "and verify the implementation. "
                            "When truly finished, respond with "
                            "TASK_COMPLETE."
                        ),
                    )

                    continue

                # ------------------------------------------------------
                # Execute every tool call.
                # ------------------------------------------------------

                for tool_call in tool_calls:

                    tool_call_id = tool_call.get(
                        "id",
                        "",
                    )

                    result = self.execute_tool_call(
                        tool_call
                    )

                    result_text = json.dumps(
                        result,
                        ensure_ascii=False,
                        default=str,
                    )

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result_text,
                    })

                    self.log_message(
                        "tool",
                        result_text,
                        {
                            "tool_call_id":
                                tool_call_id,
                        },
                    )

                    if result.get(
                        "benchmark_termination"
                    ):

                        self.status = "ABORTED"

                        if not self.stop_reason:
                            self.stop_reason = (
                                "tool_loop"
                            )

                        break

                if self.status == "ABORTED":
                    break

        except Exception as e:

            self.status = "ERROR"

            self.stop_reason = (
                "unhandled_agent_exception"
            )

            self.final_message = (
                f"{type(e).__name__}: {e}"
            )

            self.log_event(
                "agent_exception",
                {
                    "error": (
                        f"{type(e).__name__}: {e}"
                    ),
                    "traceback": traceback.format_exc(),
                },
            )

        self.finished_at = utc_now_iso()

        total_duration = (
            monotonic()
            - self.started_monotonic
        )

        report = self.build_report(
            total_duration
        )

        atomic_write_text(
            self.run_dir / "report.json",
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        )

        # If the caller supplied the persistent model progress, the caller owns
        # its lifetime so verification and model unload can remain on the same line.
        if self.progress and progress is None:
            final_label = f"Модель завершена: {self.model_key} ({self.status})"
            self.progress.stop(final_label)

        return report

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def build_report(
        self,
        total_duration: float,
    ) -> dict[str, Any]:

        average_tps = None

        if self.tokens_per_second_values:

            average_tps = (
                sum(
                    self.tokens_per_second_values
                )
                /
                len(
                    self.tokens_per_second_values
                )
            )

        average_ttft = None

        if self.ttft_values:

            average_ttft = (
                sum(self.ttft_values)
                /
                len(self.ttft_values)
            )

        project_files = []

        try:

            for item in self.project_root.rglob("*"):

                if (
                    item.is_file()
                    and ".benchmark" not in item.parts
                ):

                    try:

                        rel = item.relative_to(
                            self.project_root
                        )

                        project_files.append({
                            "path": str(rel),
                            "bytes": item.stat().st_size,
                        })

                    except Exception:
                        pass

        except Exception:
            pass

        return {
            "benchmark": {
                "status": self.status,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "duration_seconds": total_duration,
                "duration_human": human_seconds(
                    total_duration
                ),
                "stop_reason": self.stop_reason,
            },

            "model": {
                "key": self.model_key,
                "context_length_requested":
                    self.context_length,
                "metadata":
                    self.model_metadata,
            },

            "agent": {
                "iterations":
                    self.iterations,

                "tool_calls":
                    self.tool_calls,

                "successful_tool_calls":
                    self.successful_tool_calls,

                "failed_tool_calls":
                    self.failed_tool_calls,

                "file_operations":
                    self.executor.file_operations,

                "powershell_commands":
                    self.executor.command_operations,

                "idle_periods":
                    self.idle_periods,
                "compaction_count": self.compaction_count,
                "compaction_prompt_tokens": self.compaction_prompt_tokens,
                "compaction_output_tokens": self.compaction_output_tokens,
                "last_prompt_tokens": self.last_prompt_tokens,
                "loop_history": self.loop_history,
                "max_single_response_chars": MAX_SINGLE_RESPONSE_CHARS,
                "model_request_timeout_seconds": MODEL_REQUEST_TIMEOUT_SECONDS,
            },

            "tokens": {
                "prompt_tokens":
                    self.total_prompt_tokens,

                "completion_tokens":
                    self.total_completion_tokens,

                "reasoning_tokens":
                    self.total_reasoning_tokens,

                "total_tokens":
                    (
                        self.total_prompt_tokens
                        +
                        self.total_completion_tokens
                    ),

                "output_chars":
                    self.total_output_chars,

                "average_ttft_seconds":
                    average_ttft,

                "average_tokens_per_second":
                    average_tps,

                "ttft_samples":
                    self.ttft_values,

                "tokens_per_second_samples":
                    self.tokens_per_second_values,
            },

            "project": {
                "root":
                    str(self.project_root),

                "file_count":
                    len(project_files),

                "files":
                    project_files,
            },

            "final_message":
                self.final_message,
        }


# ============================================================================
# WORKSPACE MANAGEMENT
# ============================================================================

def prepare_model_workspace(
    model_key: str,
) -> tuple[Path, Path]:

    model_dir_name = safe_filename(
        model_key
    )

    model_dir = (
        RESULTS_DIR
        / model_dir_name
    )

    # --------------------------------------------------------------
    # If an old result exists and fresh mode is enabled,
    # preserve it rather than silently deleting it.
    # --------------------------------------------------------------

    if (
        model_dir.exists()
        and FRESH_MODEL_WORKSPACE
    ):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        archived = (
            RESULTS_DIR
            /
            f"{model_dir_name}__previous_{timestamp}"
        )

        counter = 1

        while archived.exists():

            archived = (
                RESULTS_DIR
                /
                f"{model_dir_name}__previous_{timestamp}_{counter}"
            )

            counter += 1

        model_dir.rename(
            archived
        )

    model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    project_dir = (
        model_dir
        / "project"
    )

    project_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    copy_reference_architecture(project_dir)
    return model_dir, project_dir


def copy_reference_architecture(project_dir: Path) -> None:
    """Copy benchmark/analyzer source into the model workspace as examples."""
    reference_dir = project_dir / "_reference_architecture"
    benchmark_dir = reference_dir / "benchmark"
    analyzer_dir = reference_dir / "analyzer"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    analyzer_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), benchmark_dir / "benchmark.py")

    candidates = ("analyzer.py", "benchmark_analyzer.py", "analyzer_final.py", "analyzer_v5.py", "analyzer_v4.py")
    analyzer_source = next((SCRIPT_DIR / name for name in candidates if (SCRIPT_DIR / name).is_file()), None)
    if analyzer_source is not None:
        shutil.copy2(analyzer_source, analyzer_dir / "analyzer.py")
    else:
        (analyzer_dir / "README.md").write_text(
            "Analyzer source was not found beside the benchmark script.\n",
            encoding="utf-8",
        )
    (reference_dir / "README.md").write_text(
        "# Reference architecture examples\n\n"
        "Copied benchmark/analyzer source for architectural reference only.\n"
        "This folder is not part of the requested deliverable. Do not copy it wholesale into the agent core.\n",
        encoding="utf-8",
    )


# ============================================================================
# PROMPT FILES
# ============================================================================

def read_required_file(
    path: Path,
    description: str,
) -> str:

    if not path.exists():

        raise FileNotFoundError(
            f"{description} not found:\n{path}"
        )

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if not text.strip():

        raise ValueError(
            f"{description} is empty:\n{path}"
        )

    return text


def write_human_report(
    report: dict[str, Any],
    path: Path,
) -> None:

    model = report.get(
        "model",
        {},
    )

    benchmark = report.get(
        "benchmark",
        {},
    )

    agent = report.get(
        "agent",
        {},
    )

    tokens = report.get(
        "tokens",
        {},
    )

    project = report.get(
        "project",
        {},
    )

    lines = []

    lines.append(
        "# LM Studio Local Agent Benchmark"
    )
    lines.append("")

    lines.append(
        f"## Model: `{model.get('key')}`"
    )
    lines.append("")

    lines.append(
        f"- Status: **{benchmark.get('status')}**"
    )

    lines.append(
        f"- Stop reason: `{benchmark.get('stop_reason')}`"
    )

    lines.append(
        f"- Runtime: "
        f"**{benchmark.get('duration_human')}**"
    )

    lines.append(
        f"- Context requested: "
        f"`{model.get('context_length_requested')}`"
    )

    lines.append("")

    lines.append("## Agent")

    lines.append(
        f"- Iterations: "
        f"{agent.get('iterations')}"
    )

    lines.append(
        f"- Tool calls: "
        f"{agent.get('tool_calls')}"
    )

    lines.append(
        f"- Successful tool calls: "
        f"{agent.get('successful_tool_calls')}"
    )

    lines.append(
        f"- Failed tool calls: "
        f"{agent.get('failed_tool_calls')}"
    )

    lines.append(
        f"- File operations: "
        f"{agent.get('file_operations')}"
    )

    lines.append(
        f"- PowerShell commands: "
        f"{agent.get('powershell_commands')}"
    )

    lines.append("")

    lines.append("## Tokens")

    lines.append(
        f"- Prompt: "
        f"{tokens.get('prompt_tokens')}"
    )

    lines.append(
        f"- Completion: "
        f"{tokens.get('completion_tokens')}"
    )

    lines.append(
        f"- Reasoning: "
        f"{tokens.get('reasoning_tokens')}"
    )

    lines.append(
        f"- Total: "
        f"{tokens.get('total_tokens')}"
    )

    lines.append(
        f"- Average TTFT: "
        f"{tokens.get('average_ttft_seconds')}"
    )

    lines.append(
        f"- Average generation speed: "
        f"{tokens.get('average_tokens_per_second')}"
    )

    lines.append("")

    lines.append("## Project")

    lines.append(
        f"- Files: "
        f"{project.get('file_count')}"
    )

    lines.append("")

    lines.append("## Final message")

    lines.append("")

    lines.append(
        report.get(
            "final_message",
            "",
        )
    )

    atomic_write_text(
        path,
        "\n".join(lines),
    )


# ============================================================================
# INDEPENDENT POST-COMPLETION VERIFICATION
# ============================================================================

def load_verification_commands(project_root: Path) -> list[str]:
    """Load explicit verification commands, or use a conservative Python fallback."""
    if VERIFICATION_FILE.exists():
        commands = []
        for line in VERIFICATION_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
        return commands

    # The current benchmark task is Python and explicitly requires unittest.
    # Only auto-enable this fallback when Python sources/tests are actually present.
    py_files = list(project_root.rglob("*.py"))
    has_tests_dir = (project_root / "tests").is_dir()
    has_test_files = any(p.name.startswith("test_") or p.name.endswith("_test.py") for p in py_files)
    if py_files and (has_tests_dir or has_test_files):
        return ["python -m unittest discover -v"]

    return []


def command_result_to_dict(result: CommandResult) -> dict[str, Any]:
    """Serialize CommandResult without pretending it is a mapping."""
    return {
        "command": result.command,
        "cwd": str(result.cwd),
        "timeout_seconds": result.timeout_seconds,
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "duration_seconds": result.duration_seconds,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "exception": result.exception,
        "stdout_chars": len(result.stdout or ""),
        "stderr_chars": len(result.stderr or ""),
        "stdout": (result.stdout or "")[:MAX_LOGGED_COMMAND_OUTPUT_CHARS],
        "stderr": (result.stderr or "")[:MAX_LOGGED_COMMAND_OUTPUT_CHARS],
        "success": (
            result.exception is None
            and not result.timed_out
            and result.exit_code == 0
        ),
    }


def run_independent_verification(
    project_root: Path,
    run_dir: Path,
) -> dict[str, Any]:
    commands = load_verification_commands(project_root)
    result: dict[str, Any] = {
        "enabled": bool(commands),
        "commands": commands,
        "passed": None,
        "results": [],
    }

    if not commands:
        result["reason"] = "No verification commands configured or auto-detected."
        return result

    for command in commands:
        started = monotonic()
        raw_command_result = run_hidden_powershell(
            project_root,
            command,
            MAX_SINGLE_COMMAND_SECONDS,
        )
        command_result = command_result_to_dict(raw_command_result)
        command_result["command"] = command
        command_result["duration_seconds"] = monotonic() - started
        result["results"].append(command_result)

        if not command_result.get("success"):
            result["passed"] = False
            break

    else:
        result["passed"] = True

    atomic_write_text(
        run_dir / "verification.json",
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
    )
    return result


# ============================================================================
# FULL BENCHMARK REPORT
# ============================================================================

def collect_reports() -> list[dict[str, Any]]:

    reports = []

    if not RESULTS_DIR.exists():
        return reports

    for report_path in RESULTS_DIR.rglob(
        "report.json"
    ):

        # Ignore archived folders.
        if "__previous_" in str(
            report_path.parent
        ):
            continue

        try:

            report = json.loads(
                report_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )

            report["_report_path"] = str(
                report_path
            )

            reports.append(
                report
            )

        except Exception as e:

            reports.append({
                "_report_path": str(report_path),
                "error": str(e),
            })

    return reports


def build_full_report(
    reports: list[dict[str, Any]],
    task: str,
    system_prompt: str,
) -> str:

    lines = []

    lines.append(
        "# LOCAL LM STUDIO AGENT BENCHMARK"
    )

    lines.append("")

    lines.append(
        f"Generated: {utc_now_iso()}"
    )

    lines.append("")

    lines.append(
        "## Test configuration"
    )

    lines.append("")

    lines.append(
        f"- LM Studio: `{LM_STUDIO_BASE}`"
    )

    lines.append(
        f"- Temperature: `{TEMPERATURE}`"
    )

    lines.append(
        f"- Maximum iterations: `{MAX_AGENT_ITERATIONS}`"
    )

    lines.append(
        f"- Maximum tool calls: `{MAX_TOTAL_TOOL_CALLS}`"
    )

    lines.append(
        f"- Flash Attention: `{USE_FLASH_ATTENTION}`"
    )

    lines.append(
        f"- KV cache GPU offload requested: "
        f"`{OFFLOAD_KV_CACHE_TO_GPU}`"
    )
    lines.append(
        f"- Model request timeout: `{MODEL_REQUEST_TIMEOUT_SECONDS}s`"
    )
    lines.append(
        f"- Max single streamed response: `{MAX_SINGLE_RESPONSE_CHARS}` chars"
    )
    lines.append(
        f"- Max total runtime: `{MAX_TOTAL_RUNTIME_SECONDS}s`"
    )
    lines.append(
        f"- Context compaction: `{ENABLE_CONTEXT_COMPACTION}` "
        f"at `{CONTEXT_COMPACTION_TRIGGER_RATIO:.0%}`"
    )
    lines.append(
        f"- Stagnant identical-tool threshold: `{MAX_STAGNANT_IDENTICAL_TOOL_CALLS}`"
    )

    lines.append("")

    lines.append(
        "## Models tested"
    )

    lines.append("")

    lines.append(
        "| Model | Status | Runtime | Iterations | "
        "Tools | Prompt tokens | Output tokens | "
        "Reasoning | Avg tok/s | TTFT | Files | PowerShell |"
    )

    lines.append(
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )

    for report in reports:

        if "error" in report:
            continue

        benchmark = report.get(
            "benchmark",
            {},
        )

        model = report.get(
            "model",
            {},
        )

        agent = report.get(
            "agent",
            {},
        )

        tokens = report.get(
            "tokens",
            {},
        )

        project = report.get(
            "project",
            {},
        )
        verification = report.get("verification") or {}

        lines.append(
            "| "
            f"`{model.get('key')}` | "
            f"{benchmark.get('status')} | "
            f"{benchmark.get('duration_human')} | "
            f"{agent.get('iterations')} | "
            f"{agent.get('tool_calls')} | "
            f"{tokens.get('prompt_tokens')} | "
            f"{tokens.get('completion_tokens')} | "
            f"{tokens.get('reasoning_tokens')} | "
            f"{tokens.get('average_tokens_per_second')} | "
            f"{tokens.get('average_ttft_seconds')} | "
            f"{project.get('file_count')} | "
            f"{agent.get('powershell_commands')} |"
        )

    lines.append("")

    lines.append(
        "## Detailed results"
    )

    lines.append("")

    for report in reports:

        if "error" in report:
            continue

        model = report.get(
            "model",
            {},
        )

        benchmark = report.get(
            "benchmark",
            {},
        )

        agent = report.get(
            "agent",
            {},
        )

        tokens = report.get(
            "tokens",
            {},
        )

        project = report.get(
            "project",
            {},
        )

        lines.append(
            f"### {model.get('key')}"
        )

        lines.append("")

        lines.append(
            f"- Status: `{benchmark.get('status')}`"
        )

        lines.append(
            f"- Stop reason: "
            f"`{benchmark.get('stop_reason')}`"
        )

        lines.append(
            f"- Runtime: "
            f"`{benchmark.get('duration_human')}`"
        )

        lines.append(
            f"- Requested context: "
            f"`{model.get('context_length_requested')}`"
        )
        load_info = report.get("model_load", {}).get("response", {}) if isinstance(report.get("model_load"), dict) else {}
        effective = load_info.get("load_config") or load_info.get("config") or {}
        if effective:
            lines.append(f"- Effective load config: `{json.dumps(effective, ensure_ascii=False, default=str)}`")

        lines.append("")

        lines.append(
            "#### Agent statistics"
        )

        lines.append("")

        lines.append(
            f"- Iterations: "
            f"{agent.get('iterations')}"
        )

        lines.append(
            f"- Tool calls: "
            f"{agent.get('tool_calls')}"
        )

        lines.append(
            f"- Successful tool calls: "
            f"{agent.get('successful_tool_calls')}"
        )

        lines.append(
            f"- Failed tool calls: "
            f"{agent.get('failed_tool_calls')}"
        )

        lines.append(
            f"- File operations: "
            f"{agent.get('file_operations')}"
        )

        lines.append(
            f"- PowerShell commands: "
            f"{agent.get('powershell_commands')}"
        )
        lines.append(
            f"- Context compactions: {agent.get('compaction_count', 0)}"
        )
        lines.append(
            f"- Compaction prompt tokens: {agent.get('compaction_prompt_tokens', 0)}"
        )
        lines.append(
            f"- Compaction output tokens: {agent.get('compaction_output_tokens', 0)}"
        )

        lines.append("")

        lines.append(
            "#### Token statistics"
        )

        lines.append("")

        lines.append(
            f"- Prompt tokens: "
            f"{tokens.get('prompt_tokens')}"
        )

        lines.append(
            f"- Completion tokens: "
            f"{tokens.get('completion_tokens')}"
        )

        lines.append(
            f"- Reasoning tokens: "
            f"{tokens.get('reasoning_tokens')}"
        )

        lines.append(
            f"- Total tokens: "
            f"{tokens.get('total_tokens')}"
        )

        lines.append(
            f"- Average tokens/sec: "
            f"{tokens.get('average_tokens_per_second')}"
        )

        lines.append(
            f"- Average TTFT: "
            f"{tokens.get('average_ttft_seconds')}"
        )

        lines.append("")

        lines.append(
            "#### Project"
        )

        lines.append("")

        lines.append(
            f"- Files created/present: "
            f"{project.get('file_count')}"
        )

        lines.append("")

        verification = report.get("verification") or {}
        lines.append("#### Independent verification")
        lines.append("")
        lines.append(f"- Enabled: `{verification.get('enabled', False)}`")
        lines.append(f"- Passed: `{verification.get('passed')}`")
        if verification.get("commands"):
            for command in verification.get("commands", []):
                lines.append(f"- Command: `{command}`")
        lines.append("")

        lines.append(
            "#### Final model message"
        )

        lines.append("")

        lines.append(
            report.get(
                "final_message",
                "",
            )
        )

        lines.append("")

        lines.append(
            f"Raw report: `{report.get('_report_path')}`"
        )

        lines.append("")

        lines.append("---")

        lines.append("")

    lines.append(
        "## Raw task"
    )

    lines.append("")

    lines.append("```text")

    lines.append(task)

    lines.append("```")

    lines.append("")

    lines.append(
        "## System prompt used"
    )

    lines.append("")

    lines.append("```text")

    lines.append(system_prompt)

    lines.append("```")

    lines.append("")

    return "\n".join(lines)


# ============================================================================
# CONSOLE OUTPUT
# ============================================================================

def print_header() -> None:

    print()
    print("=" * 80)
    print(" LM STUDIO LOCAL AGENT BENCHMARK")
    print("=" * 80)
    print()
    print(f"Script:       {SCRIPT_DIR}")
    print(f"LM Studio:    {LM_STUDIO_BASE}")
    print(f"Config:       {CONFIG_DIR}")
    print(f"Results:      {RESULTS_DIR}")
    print()


def print_model_info(
    model: dict[str, Any],
    context_length: Optional[int],
    context_source: str,
) -> None:

    print()
    print("-" * 80)

    print(
        f"Model:        {model.get('key')}"
    )

    print(
        f"Display name: {model.get('display_name')}"
    )

    print(
        f"Parameters:   {model.get('params_string')}"
    )

    quant = model.get(
        "quantization"
    )

    if isinstance(quant, dict):

        print(
            f"Quantization: {quant.get('name')}"
        )

    print(
        f"Context:      {context_length}"
    )

    print(
        f"Context src:  {context_source}"
    )

    print("-" * 80)


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:

    print_header()

    # ------------------------------------------------------------------
    # Validate configuration files
    # ------------------------------------------------------------------

    try:

        system_prompt = read_required_file(
            SYSTEM_PROMPT_FILE,
            "system_prompt.txt",
        )

        task = read_required_file(
            TASK_FILE,
            "task.txt",
        )

    except Exception as e:

        print()
        print("CONFIGURATION ERROR")
        print()
        print(str(e))
        print()
        return 1

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # LM Studio client
    # ------------------------------------------------------------------

    client = LMStudioClient(
        LM_STUDIO_BASE,
        LM_API_TOKEN,
    )

    # ------------------------------------------------------------------
    # Test server
    # ------------------------------------------------------------------

    try:

        models = discover_models(
            client
        )

    except Exception as e:

        print()
        print("LM STUDIO CONNECTION ERROR")
        print()
        print(str(e))
        print()
        print(
            "Make sure LM Studio Developer Server "
            "is running at:"
        )
        print(
            f"    {LM_STUDIO_BASE}"
        )
        print()

        return 2

    print(
        f"Models discovered in LM Studio: "
        f"{len(models)}"
    )

    print("Native-tool benchmark mode: enabled")

    print()

    # ------------------------------------------------------------------
    # Remove excluded models
    # ------------------------------------------------------------------

    selected_models = []

    for model in models:

        model_key = str(model.get("key", "")).strip()
        model_type = str(model.get("type", "")).strip().lower()

        if not model_key:
            continue

        if model_type not in {"llm", "language"}:
            print(f"[SKIP] Not an LLM: {model_key}")
            continue

        if model_key.lower() in {
            x.lower()
            for x in EXCLUDED_MODELS
        }:
            print(f"[SKIP] Explicitly excluded: {model_key}")
            continue

        native_tools, tool_source, tool_metadata = discover_native_tool_support(
            client,
            model,
        )

        model["_native_tool_use"] = native_tools
        model["_native_tool_use_source"] = tool_source
        model["_native_tool_use_metadata"] = tool_metadata

        if not native_tools:
            print(f"[SKIP] No native tool use: {model_key} ({tool_source})")
            continue

        print(f"[SELECT] {model_key} | native tools: {tool_source}")
        selected_models.append(model)

    if not selected_models:

        print(
            "No usable models found."
        )

        return 3

    # ------------------------------------------------------------------
    # Global run log
    # ------------------------------------------------------------------

    global_run = {
        "started_at": utc_now_iso(),
        "models_requested": [str(model.get("key")) for model in models],
        "models_selected": [
            model.get("key")
            for model in selected_models
        ],
        "configuration": {
            "offload_kv_cache_to_gpu_requested": OFFLOAD_KV_CACHE_TO_GPU,
            "flash_attention": USE_FLASH_ATTENTION,
            "model_request_timeout_seconds": MODEL_REQUEST_TIMEOUT_SECONDS,
            "max_single_response_chars": MAX_SINGLE_RESPONSE_CHARS,
            "max_total_runtime_seconds": MAX_TOTAL_RUNTIME_SECONDS,
            "context_compaction_enabled": ENABLE_CONTEXT_COMPACTION,
            "context_compaction_trigger_ratio": CONTEXT_COMPACTION_TRIGGER_RATIO,
            "max_stagnant_identical_tool_calls": MAX_STAGNANT_IDENTICAL_TOOL_CALLS,
        },
    }

    atomic_write_text(
        RESULTS_DIR / "benchmark_run.json",
        json.dumps(
            global_run,
            ensure_ascii=False,
            indent=2,
        ),
    )

    # ------------------------------------------------------------------
    # Run every model
    # ------------------------------------------------------------------

    completed_reports = []

    for index, model in enumerate(
        selected_models,
        start=1,
    ):

        model_key = str(
            model.get("key")
        )

        print()
        print(
            f"[{index}/{len(selected_models)}] "
            f"Preparing {model_key}"
        )

        # --------------------------------------------------------------
        # Discover maximum context
        # --------------------------------------------------------------

        try:

            context_length, context_source, metadata = (
                discover_max_context(
                    client,
                    model,
                )
            )

        except Exception as e:

            context_length = None
            context_source = (
                f"discovery failed: {e}"
            )
            metadata = model

        print_model_info(
            metadata,
            context_length,
            context_source,
        )

        # --------------------------------------------------------------
        # Workspace
        # --------------------------------------------------------------

        try:

            model_dir, project_dir = (
                prepare_model_workspace(
                    model_key
                )
            )

        except Exception as e:

            print(
                f"[ERROR] Cannot prepare workspace: "
                f"{e}"
            )

            continue

        run_metadata = {
            "model": model_key,
            "model_metadata": metadata,
            "context_length": context_length,
            "context_source": context_source,
            "native_tool_use": model.get("_native_tool_use"),
            "native_tool_use_source": model.get("_native_tool_use_source"),
            "started_at": utc_now_iso(),
            "project_dir": str(project_dir),
        }

        atomic_write_text(
            model_dir / "run_metadata.json",
            json.dumps(
                run_metadata,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        )

        # Save exact inputs used by the benchmark.
        atomic_write_text(
            model_dir / "system_prompt.txt",
            system_prompt,
        )

        atomic_write_text(
            model_dir / "task.txt",
            task,
        )

        # --------------------------------------------------------------
        # One persistent progress line for this entire model.
        # --------------------------------------------------------------

        model_progress = ConsoleProgress(model_key)
        model_progress.start()
        model_progress.set_stage("Выгрузка предыдущих моделей")

        # --------------------------------------------------------------
        # Unload everything
        # --------------------------------------------------------------

        print("[LM Studio] Unloading all loaded models...")

        try:

            model_progress.set_stage("Выгрузка предыдущих моделей")
            unloaded = unload_all_models(client)

            atomic_write_text(
                model_dir / "unload_before_load.json",
                json.dumps(
                    unloaded,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            )

        except Exception as e:

            print(
                f"[WARNING] Could not unload all models: "
                f"{e}"
            )

        # --------------------------------------------------------------
        # Load current model
        # --------------------------------------------------------------

        print(
            "[LM Studio] Loading model..."
        )

        load_started = monotonic()

        try:

            model_progress.set_stage("Загрузка модели")
            load_response = load_model(client, model_key, context_length)

            load_duration = (
                monotonic()
                - load_started
            )

            print(
                f"[LM Studio] Loaded in "
                f"{load_duration:.2f}s"
            )

            atomic_write_text(
                model_dir / "load_response.json",
                json.dumps(
                    load_response,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            )

            # Verify the effective configuration returned by LM Studio instead
            # of trusting our request payload. This catches accidental runs of
            # stale scripts/configurations immediately.
            effective_load = load_response.get("load_config") or load_response.get("config") or {}
            effective_kv = effective_load.get("offload_kv_cache_to_gpu")
            if effective_kv is not None and bool(effective_kv) != OFFLOAD_KV_CACHE_TO_GPU:
                print(
                    f"[WARNING] LM Studio effective KV offload is {effective_kv}, "
                    f"requested {OFFLOAD_KV_CACHE_TO_GPU}."
                )
            atomic_write_text(
                model_dir / "effective_load_config.json",
                json.dumps(effective_load, ensure_ascii=False, indent=2, default=str),
            )

        except Exception as e:

            print(
                "[ERROR] Model loading failed:"
            )

            print(str(e))

            atomic_write_text(
                model_dir / "load_error.txt",
                traceback.format_exc(),
            )

            model_progress.stop("Загрузка модели не удалась")
            continue

        # --------------------------------------------------------------
        # Agent
        # --------------------------------------------------------------

        print()
        print("[AGENT] Starting autonomous task...")
        model_progress.set_stage("Запуск автономного агента")

        agent = BenchmarkAgent(
            client=client,
            model_key=model_key,
            model_metadata=metadata,
            context_length=context_length,
            system_prompt=system_prompt,
            task=task,
            project_root=project_dir,
            run_dir=model_dir,
        )

        report = agent.run(progress=model_progress)

        # Model self-report is not sufficient for benchmark success. When the
        # agent declares completion, run an independent verification command set
        # outside the model's conversation.
        if report.get("benchmark", {}).get("status") == "SUCCESS":
            model_progress.set_stage("Независимая проверка")
            try:
                verification = run_independent_verification(project_dir, model_dir)
                report["verification"] = verification
                if verification.get("enabled") and not verification.get("passed"):
                    report["benchmark"]["status"] = "VERIFICATION_FAILED"
                    report["benchmark"]["stop_reason"] = "independent_verification_failed"
            except Exception as e:
                report["verification"] = {
                    "enabled": True,
                    "passed": False,
                    "error": f"{type(e).__name__}: {e}",
                }
                report["benchmark"]["status"] = "VERIFICATION_ERROR"
                report["benchmark"]["stop_reason"] = "independent_verification_error"

        # Add load statistics.
        report["model_load"] = {
            "duration_seconds":
                load_response.get(
                    "load_time_seconds",
                    load_duration,
                ),
            "response":
                load_response,
        }

        atomic_write_text(
            model_dir / "report.json",
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
        )

        write_human_report(
            report,
            model_dir / "REPORT.md",
        )

        completed_reports.append(
            report
        )

        print()
        print(
            f"[RESULT] {model_key}"
        )

        print(
            f"Status:    "
            f"{report['benchmark']['status']}"
        )

        print(
            f"Runtime:   "
            f"{report['benchmark']['duration_human']}"
        )

        print(
            f"Iterations:"
            f" {report['agent']['iterations']}"
        )

        print(
            f"Tools:     "
            f"{report['agent']['tool_calls']}"
        )

        print(
            f"Tokens:    "
            f"{report['tokens']['total_tokens']}"
        )

        # --------------------------------------------------------------
        # Unload after benchmark
        # --------------------------------------------------------------

        print(
            "[LM Studio] Unloading model..."
        )

        try:

            model_progress.set_stage("Выгрузка модели")
            unload_after = unload_all_models(client)

            atomic_write_text(
                model_dir / "unload_after.json",
                json.dumps(
                    unload_after,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
            )

        except Exception as e:

            print(
                f"[WARNING] Unload failed: {e}"
            )

        model_progress.stop(f"Модель завершена: {model_key} ({report['benchmark']['status']})")
        print(f"[DONE] {model_key}")

    # ------------------------------------------------------------------
    # Collect every report from disk.
    #
    # This deliberately does NOT rely only on the current process,
    # so if the script is interrupted and restarted, existing reports
    # remain available.
    # ------------------------------------------------------------------

    all_reports = collect_reports()

    # ------------------------------------------------------------------
    # Final report
    # ------------------------------------------------------------------

    full_report = build_full_report(
        all_reports,
        task,
        system_prompt,
    )

    final_report_path = (
        SCRIPT_DIR
        / "FULL_BENCHMARK_REPORT.md"
    )

    atomic_write_text(
        final_report_path,
        full_report,
    )

    # Machine-readable final report.
    atomic_write_text(
        SCRIPT_DIR
        / "FULL_BENCHMARK_REPORT.json",
        json.dumps(
            all_reports,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
    )

    print()
    print("=" * 80)
    print(" BENCHMARK FINISHED")
    print("=" * 80)
    print()

    print(
        f"Models completed: "
        f"{len(completed_reports)}"
    )

    print(
        f"Final report:"
    )

    print(
        f"    {final_report_path}"
    )

    print()

    return 0


if __name__ == "__main__":

    try:
        raise SystemExit(
            main()
        )

    except KeyboardInterrupt:

        print()
        print(
            "Benchmark interrupted by user."
        )

        raise SystemExit(130)

    except Exception:

        print()
        print(
            "FATAL BENCHMARK ERROR"
        )

        traceback.print_exc()

        raise SystemExit(100)
