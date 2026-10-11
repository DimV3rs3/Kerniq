#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent multi-judge analyzer for the LM Studio coding-agent benchmark (v9).

Pipeline
0. Static analysis (ast) + unittest/coverage of every generated project - objective facts, no LLM.
1. Judges (one model loaded at a time, fresh chat per project) audit each project against a rubric:
   requirement matrix + 7 engineering dimensions (architecture, extensibility/scalability, code quality,
   robustness, tests, docs, constraint compliance). They can run their own probes (timing, bad input).
2. A script validates every cited evidence reference, applies hard caps from the facts and computes the
   scores (weighted medians). No LLM does arithmetic or ranking.
3. The strongest model only writes an interpretation (Russian) from the computed data set.
4. FULL_ANALYSIS_REPORT.md, RANKING.json, RANKING.csv are rendered deterministically.

Useful flags: --rescore (rebuild report from stored audits, no models), --final-only, --skip-final, --no-resume.
See CHANGELOG at the bottom of this file.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import http.client
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = SCRIPT_DIR / "config"
RESULTS_DIR = SCRIPT_DIR / "benchmark_results"
ANALYSIS_DIR = RESULTS_DIR / "_analysis"
TASK_FILE = CONFIG_DIR / "task.txt"
SYSTEM_PROMPT_FILE = CONFIG_DIR / "system_prompt.txt"
ANALYZER_SYSTEM_PROMPT_FILE = CONFIG_DIR / "analyzer_system_prompt.txt"
ANALYZER_TASK_FILE = CONFIG_DIR / "analyzer_task.txt"

LM_STUDIO_BASE = os.environ.get("LM_STUDIO_BASE", "http://127.0.0.1:1234").rstrip("/")

# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
# Reviewer label = fixed position in this list (ANALYST_001 is always the first
# entry), so labels stay stable between runs and resume keeps working even if a
# model is temporarily unavailable.
REVIEWER_PRIMARY_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.5-9b",
    "google/gemma-4-12b",
    "mistralai/ministral-3-14b-reasoning",
]
REVIEWER_RESERVE_MODELS = [
    "qwen/qwen3.5-9b-coder",
    "qwen/qwen3-coder-30b",
]
# False = a missing primary reviewer is simply skipped (original behaviour).
USE_RESERVE_REVIEWERS = False

FINAL_PRIMARY_MODEL = "qwen/qwen3-coder-next"
FINAL_RESERVE_MODELS = [
    "qwen/qwen3-coder-30b",
    "mistralai/devstral-small-2-2512",
    "openai/gpt-oss-20b",
]

# --------------------------------------------------------------------------
# Sampling / generation
# --------------------------------------------------------------------------
# Very low temperature makes gpt-oss (and most small models) far more prone to
# repetition loops. 0.3 is still stable enough for auditing.
ANALYZER_TEMPERATURE = 0.3
# "low" | "medium" | "high" for models that support it (gpt-oss). None = default.
ANALYZER_REASONING_EFFORT: Optional[str] = None
# Cap for ONE model turn (reasoning + answer). None = unbounded.
MAX_COMPLETION_TOKENS: Optional[int] = 20_000
# The judge does not need the model's absolute maximum context; a smaller
# window means faster prompt processing and less VRAM. None = model maximum.
ANALYZER_CONTEXT_LENGTH_CAP: Optional[int] = None

# Runaway guards applied while streaming a single response.
MAX_STREAM_CONTENT_CHARS = 80_000
MAX_STREAM_REASONING_CHARS = 120_000

# --------------------------------------------------------------------------
# Agent-loop budgets
# --------------------------------------------------------------------------
MAX_AUDITOR_ITERATIONS = 200
SOFT_TOOL_BUDGET = 40          # model is told to wrap up
MAX_AUDITOR_TOOL_CALLS = 100    # hard stop for new tool work
MAX_AUDIT_SECONDS = 60 * 60
MAX_FINAL_ITERATIONS = 400
MAX_FINAL_TOOL_CALLS = 400
MAX_FINAL_SECONDS = 120 * 60
MAX_FINAL_NUDGES = 3           # how many times an answer may be bounced back
MAX_BAD_TURNS = 3              # runaway / empty turns before forced finalize
MAX_IDENTICAL_TOOL_CALLS = 3   # total occurrences of one identical call
MIN_AUDIT_CHARS = 1500
MIN_AUDIT_READS = 3
MIN_FINAL_CHARS = 3000
CHARS_PER_TOKEN = 3.0          # conservative estimate for code/JSON

# --------------------------------------------------------------------------
# Tool limits
# --------------------------------------------------------------------------
MAX_READ_CHARS_PER_CALL = 30_000
MAX_TOOL_RESULT_CHARS = 40_000
MAX_SEARCH_RESULTS = 60
MAX_TREE_ENTRIES = 300
MAX_FILE_SIZE_FOR_DIRECT_READ = 5_000_000
MAX_TEXT_LOAD_CHARS = 20_000_000
UNITTEST_TIMEOUT_SECONDS = 180

# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
RESUME = True
ENABLE_PROMPT_LOGGER = False
PROMPT_LOG_DIR = RESULTS_DIR / "_prompt_logs"
UNLOAD_POLL_SECONDS = 60
UNLOAD_POLL_INTERVAL = 1.0
USE_FLASH_ATTENTION = True
OFFLOAD_KV_CACHE_TO_GPU = True
EVAL_BATCH_SIZE = None
NUM_EXPERTS = None

# Directories that are noise everywhere (tree/search/unittest copy).
IGNORED_DIRS = {"__pycache__", ".git", ".idea", ".vs", "node_modules", ".venv", "venv"}
# Directories judges must never see (other judges' reports => no independence).
HIDDEN_DIRS = {"_analys"}

COMPLETED_STATUSES = {"ANALYZED", "ANALYZED_FORCED", "ANALYZED_LOW_EVIDENCE", "ANALYZED_TRIVIAL"}
READ_TOOLS = {"read_file", "read_lines", "read_json", "read_report", "read_report_json"}
SCHEMA_VERSION = 9
STATIC_DIR = ANALYSIS_DIR / "static"
ANALYZER_EXTRA_FILE = CONFIG_DIR / "analyzer_extra.txt"   # optional extra guidance appended to the judge prompt
PROBE_TIMEOUT_SECONDS = 60
MAX_PROBES_PER_AUDIT = 8
COVERAGE_ENABLED = True        # used only if `pip install coverage` is present
MAX_REQUIREMENTS = 30


# ==========================================================================
# Small helpers
# ==========================================================================
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path, max_chars: Optional[int] = None) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    if max_chars is not None and len(data) > max_chars:
        return data[:max_chars] + f"\n\n[TRUNCATED: {len(data):,} chars]"
    return data


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", errors="replace")
    tmp.replace(path)


def jd(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def jcompact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n] + f"…[+{len(text) - n:,} chars]"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")[:180]


def reviewer_label(index: int) -> str:
    return f"ANALYST_{index:03d}"


def guess_score(text: str) -> Optional[int]:
    """Last 'NN/100' (or 'NN out of 100') found in a report, if any."""
    found = [int(m.group(1)) for m in re.finditer(r"\b(\d{1,3})\s*(?:/|out of)\s*100\b", text or "", re.I)]
    found = [v for v in found if 0 <= v <= 100]
    return found[-1] if found else None


def numeric_model_size(metadata: dict[str, Any]) -> float:
    for value in (metadata.get("params_string"), metadata.get("parameter_count"),
                  metadata.get("parameters"), metadata.get("size"), metadata.get("size_string")):
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        if isinstance(value, str):
            m = re.search(r"(\d+(?:\.\d+)?)\s*([TGMK]B?)\b", value, re.IGNORECASE)
            if m:
                mult = {"T": 1e12, "G": 1e9, "M": 1e6, "K": 1e3}[m.group(2)[0].upper()]
                return float(m.group(1)) * mult
    return 0.0


def benchmark_summary(summary: dict[str, Any]) -> dict[str, Any]:
    b = summary.get("benchmark") or {}
    a = summary.get("agent") or {}
    t = summary.get("tokens") or {}
    p = summary.get("project") or {}
    ml = summary.get("model_load") or {}
    return {
        "benchmark": {k: b.get(k) for k in ("status", "duration_seconds", "stop_reason")},
        "agent": {k: a.get(k) for k in (
            "iterations", "tool_calls", "successful_tool_calls", "failed_tool_calls",
            "file_operations", "powershell_commands", "idle_periods", "compaction_count", "loop_history")},
        "tokens": {k: t.get(k) for k in (
            "prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens",
            "average_ttft_seconds", "average_tokens_per_second")},
        "project": {"file_count": p.get("file_count"), "files": p.get("files")},
        "verification": summary.get("verification") or {},
        "model_load": {"status": ml.get("status"), "context_length": ml.get("context_length")},
    }


def resolve_inside(root: Path, rel: str) -> Path:
    rel = (rel or "").strip().replace("\\", "/")
    p = Path(rel) if rel else Path(".")
    if p.is_absolute():
        try:
            rel = str(p.resolve().relative_to(root.resolve()))
        except ValueError:
            raise PermissionError("Path escapes the audited directory")
    candidate = (root / rel.lstrip("/")).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PermissionError("Path escapes the audited directory") from exc
    return candidate


def safe_rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError as exc:
        raise PermissionError("Path escapes the audited directory") from exc


def append_prompt_log(project: str, reviewer: str, record: dict[str, Any]) -> None:
    if not ENABLE_PROMPT_LOGGER:
        return
    out = PROMPT_LOG_DIR / safe_name(reviewer) / safe_name(project)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "prompts.jsonl").open("a", encoding="utf-8") as f:
        f.write(jcompact(record) + "\n")


# ==========================================================================
# Live one-line UI
# ==========================================================================
class LiveUI:
    """One terminal line, never wider than the console (wrapping caused the
    old 'garbage wall' on Windows), guarded by a lock (ticker thread + main
    thread used to write concurrently)."""

    def __init__(self) -> None:
        self.model = "-"
        self.phase = "idle"
        self.iteration = 0
        self.tool_calls = 0
        self.started = time.perf_counter()
        self._tail = ""
        self._active = False
        self._lock = threading.Lock()
        self._last_render = 0.0
        self._ticker: Optional[threading.Thread] = None
        self._stop_evt = threading.Event()

    def start(self, model: str, phase: str) -> None:
        self.model, self.phase = model, phase
        self.iteration = self.tool_calls = 0
        self.started = time.perf_counter()
        self._tail = ""
        self._active = True
        self._stop_evt.clear()
        self.render(force=True)
        self._ticker = threading.Thread(target=self._tick, daemon=True)
        self._ticker.start()

    def _tick(self) -> None:
        while not self._stop_evt.wait(0.25):
            self.render()

    def set_phase(self, phase: str) -> None:
        if phase != self.phase:
            self.phase = phase
            self.render(force=True)

    def set_counts(self, iteration: Optional[int] = None, tool_calls: Optional[int] = None) -> None:
        if iteration is not None:
            self.iteration = iteration
        if tool_calls is not None:
            self.tool_calls = tool_calls
        self.render(force=True)

    def feed(self, text: str) -> None:
        if text:
            self._tail = (self._tail + text)[-600:]

    def render(self, force: bool = False) -> None:
        with self._lock:
            if not self._active:
                return
            now = time.perf_counter()
            if not force and now - self._last_render < 0.1:
                return
            self._last_render = now
            elapsed = now - self.started
            cols = max(40, shutil.get_terminal_size((120, 20)).columns - 1)
            width = 12
            pos = int(elapsed * 5) % (width * 2 - 2)
            if pos >= width:
                pos = (width * 2 - 2) - pos
            bar = "░" * pos + "█" + "░" * max(0, width - pos - 1)
            head = (f"\r[{bar}] {self.model} | {self.phase:<14} | i{self.iteration:<4} t{self.tool_calls:<4} "
                    f"| {elapsed:6.0f}s | ")
            room = cols - len(head) + 1
            tail = self._tail.replace("\r", "").replace("\n", " ").replace("\x1b", "")
            tail = tail[-max(0, room -10):] if room > 0 else ""
            line = (head + tail)[: cols + 3] + "  "
            sys.stdout.write(line.ljust(cols + 1))
            sys.stdout.flush()

    def stop(self, final_phase: str = "done") -> None:
        if not self._active:
            return
        self._stop_evt.set()
        if self._ticker and self._ticker.is_alive():
            self._ticker.join(timeout=0.5)
        self.phase = final_phase
        self.render(force=True)
        with self._lock:
            self._active = False
            sys.stdout.write("\n")
            sys.stdout.flush()


# ==========================================================================
# LM Studio client
# ==========================================================================
class LMStudioError(RuntimeError):
    pass


def looks_repetitive(buf: str) -> bool:
    """True when the tail of the stream is the same ~160 chars over and over."""
    if len(buf) < 1600:
        return False
    chunk = buf[-160:]
    if not chunk.strip():
        return True
    return buf[-1600:].count(chunk) >= 6


def normalize_tool_name(name: str) -> str:
    name = (name or "").strip()
    name = name.split("<|", 1)[0].strip()          # harmony artefacts
    if name.startswith("functions."):
        name = name[len("functions."):]
    return name


class LMStudioClient:
    """http.client based (the legacy HTTP helper gets 503 on the user's box)."""

    def __init__(self, base_url: str = LM_STUDIO_BASE, token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.context_length = 0
        scheme, sep, rest = self.base_url.partition("://")
        if not sep or scheme not in ("http", "https"):
            raise ValueError(f"Unsupported LM Studio base URL: {self.base_url!r}")
        authority, _, base_path = rest.partition("/")
        if not authority:
            raise ValueError(f"Missing LM Studio host in URL: {self.base_url!r}")
        if ":" in authority:
            self._host, port = authority.rsplit(":", 1)
            self._port = int(port)
        else:
            self._host, self._port = authority, 443 if scheme == "https" else 80
        self._scheme = scheme
        self._base_path = ("/" + base_path.rstrip("/")) if base_path else ""

    def headers(self, stream: bool = False) -> dict[str, str]:
        h = {"Content-Type": "application/json",
             "Accept": "text/event-stream" if stream else "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _connection(self, timeout: Optional[float] = None):
        cls = http.client.HTTPSConnection if self._scheme == "https" else http.client.HTTPConnection
        return cls(self._host, self._port, timeout=timeout)

    def _path(self, path: str) -> str:
        return f"{self._base_path}{path}" if path.startswith("/") else f"{self._base_path}/{path}"

    def request(self, method: str, path: str, payload: Optional[dict[str, Any]] = None,
                timeout: Optional[float] = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False,
                                                       separators=(",", ":")).encode("utf-8")
        conn = self._connection(timeout)
        try:
            conn.request(method.upper(), self._path(path), body=body, headers=self.headers())
            resp = conn.getresponse()
            raw = resp.read()
            if not 200 <= resp.status < 300:
                raise LMStudioError(f"HTTP {resp.status} {method} {path}: "
                                    f"{raw.decode('utf-8', errors='replace')}")
            return json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
        except LMStudioError:
            raise
        except (OSError, http.client.HTTPException, ValueError) as exc:
            raise LMStudioError(f"LM Studio connection/parse error: {exc}") from exc
        finally:
            conn.close()

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any], timeout: Optional[float] = None) -> dict[str, Any]:
        return self.request("POST", path, payload, timeout)

    def model_catalog(self) -> list[dict[str, Any]]:
        data = self.get("/api/v1/models")
        return [m for m in data.get("models", []) if isinstance(m, dict) and m.get("key")]

    def loaded_instances(self) -> list[dict[str, Any]]:
        loaded: list[dict[str, Any]] = []
        for m in self.model_catalog():
            for inst in m.get("loaded_instances") or []:
                item = dict(inst) if isinstance(inst, dict) else {"value": inst}
                item.setdefault("model", m.get("key"))
                loaded.append(item)
        return loaded

    def unload_all_verified(self) -> list[dict[str, Any]]:
        before = self.loaded_instances()
        if not before:
            return []
        unloaded: list[dict[str, Any]] = []
        for item in before:
            instance_id = item.get("instance_id") or item.get("id") or item.get("model")
            if not instance_id:
                raise LMStudioError(f"Loaded instance has no id: {jd(item)}")
            try:
                res = self.post("/api/v1/models/unload", {"instance_id": instance_id}, timeout=300)
            except Exception as exc:
                raise LMStudioError(f"Failed to unload {instance_id!r}: {exc}") from exc
            unloaded.append({"instance_id": instance_id, "model": item.get("model"), "result": res})
        deadline = time.monotonic() + UNLOAD_POLL_SECONDS
        while True:
            try:
                last = self.loaded_instances()
            except Exception as exc:
                raise LMStudioError(f"Cannot verify model unload: {exc}") from exc
            if not last:
                return unloaded
            if time.monotonic() >= deadline:
                raise LMStudioError("Models still loaded after unload request: " + jd(last))
            time.sleep(UNLOAD_POLL_INTERVAL)

    def assert_empty(self) -> None:
        loaded = self.loaded_instances()
        if loaded:
            raise LMStudioError("REFUSING TO LOAD: LM Studio still has loaded models: " + jd(loaded))

    def load_model(self, model_key: str) -> dict[str, Any]:
        self.assert_empty()
        meta = {m.get("key"): m for m in self.model_catalog()}.get(model_key) or {}
        ctx = int(meta.get("max_context_length") or 0)
        if ctx <= 0:
            raise LMStudioError(f"LM Studio did not report max_context_length for {model_key}")
        if ANALYZER_CONTEXT_LENGTH_CAP:
            ctx = min(ctx, ANALYZER_CONTEXT_LENGTH_CAP)
        payload: dict[str, Any] = {"model": model_key, "context_length": ctx,
                                   "flash_attention": USE_FLASH_ATTENTION,
                                   "offload_kv_cache_to_gpu": OFFLOAD_KV_CACHE_TO_GPU}
        if EVAL_BATCH_SIZE is not None:
            payload["eval_batch_size"] = EVAL_BATCH_SIZE
        if NUM_EXPERTS is not None:
            payload["num_experts"] = NUM_EXPERTS
        print(f"  [LM] loading with context_length={ctx:,}")
        response = self.post("/api/v1/models/load", payload, timeout=None)
        loaded = self.loaded_instances()
        if len(loaded) != 1 or loaded[0].get("model") != model_key:
            raise LMStudioError(f"Unexpected loaded state after loading {model_key}: {jd(loaded)}")
        self.context_length = ctx
        return response

    def stream_chat(self, payload: dict[str, Any], ui: Optional[LiveUI] = None) -> dict[str, Any]:
        """Stream one chat completion with runaway protection.

        finish_reason may be: stop | tool_calls | length | runaway | None.
        'runaway' means the stream was cut by a local guard (repetition or
        oversize); the partial message must be discarded by the caller.
        """
        req = dict(payload)
        req["stream"] = True
        req.setdefault("stream_options", {"include_usage": True})
        body = json.dumps(req, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        conn = self._connection(None)

        content: list[str] = []
        reasoning_chars = 0
        content_chars = 0
        slots: list[dict[str, Any]] = []
        by_index: dict[int, int] = {}
        usage: dict[str, Any] = {}
        finish_reason: Optional[str] = None
        runaway = ""
        buf = ""
        since_check = 0
        if ui:
            ui.set_phase("prompt")

        try:
            conn.request("POST", self._path("/v1/chat/completions"), body=body,
                         headers=self.headers(stream=True))
            resp = conn.getresponse()
            if not 200 <= resp.status < 300:
                raise LMStudioError(f"HTTP {resp.status} POST /v1/chat/completions: "
                                    f"{resp.read().decode('utf-8', errors='replace')}")
            while True:
                line = resp.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(chunk.get("usage"), dict):
                    usage = chunk["usage"]
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                choice = choices[0] or {}
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta") or {}
                piece = ""

                r = delta.get("reasoning_content") or delta.get("reasoning")
                if isinstance(r, str) and r:
                    reasoning_chars += len(r)
                    piece += r
                    if ui:
                        ui.set_phase("thinking")
                        ui.feed(r)
                t = delta.get("content")
                if isinstance(t, str) and t:
                    content.append(t)
                    content_chars += len(t)
                    piece += t
                    if ui:
                        ui.set_phase("writing")
                        ui.feed(t)

                for tc in delta.get("tool_calls") or []:
                    idx = int(tc.get("index", 0) or 0)
                    tid = tc.get("id") or ""
                    slot_i = by_index.get(idx)
                    # Some servers reuse index 0 for every call and only change the id.
                    if slot_i is not None and tid and slots[slot_i]["id"] and slots[slot_i]["id"] != tid:
                        slot_i = None
                    if slot_i is None:
                        slots.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                        slot_i = len(slots) - 1
                        by_index[idx] = slot_i
                    item = slots[slot_i]
                    if tid:
                        item["id"] = tid
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        item["function"]["name"] += fn["name"]
                    if fn.get("arguments"):
                        item["function"]["arguments"] += fn["arguments"]
                        piece += fn["arguments"]
                        if ui:
                            ui.set_phase("tool call")
                            ui.feed(fn["arguments"])

                if piece:
                    buf = (buf + piece)[-2400:]
                    since_check += len(piece)
                    if since_check >= 500:
                        since_check = 0
                        if looks_repetitive(buf):
                            runaway = "repetition"
                    if content_chars > MAX_STREAM_CONTENT_CHARS:
                        runaway = "content too long"
                    if reasoning_chars > MAX_STREAM_REASONING_CHARS:
                        runaway = "reasoning too long"
                    if runaway:
                        finish_reason = "runaway"
                        break
        except LMStudioError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise LMStudioError(f"LM Studio connection error during streaming chat: {exc}") from exc
        finally:
            conn.close()   # closing the socket makes LM Studio cancel generation

        tool_calls = []
        for i, s in enumerate(slots):
            name = normalize_tool_name(s["function"]["name"])
            if not name:
                continue
            tool_calls.append({
                "id": s["id"] or f"call_{int(time.time() * 1000)}_{i}",
                "type": "function",
                "function": {"name": name, "arguments": s["function"]["arguments"] or "{}"},
            })
        message: dict[str, Any] = {"role": "assistant", "content": "".join(content)}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"message": message, "usage": usage, "finish_reason": finish_reason,
                "runaway": runaway, "reasoning_chars": reasoning_chars, "content_chars": content_chars}


# ==========================================================================


# ==========================================================================
# Static analysis (stdlib `ast`): objective facts judges must not guess
# ==========================================================================
STDLIB_FALLBACK = {
    "__future__", "abc", "argparse", "array", "ast", "asyncio", "atexit", "base64", "binascii", "bisect",
    "builtins", "bz2", "calendar", "cmd", "codecs", "collections", "colorsys", "concurrent", "configparser",
    "contextlib", "contextvars", "copy", "csv", "ctypes", "curses", "dataclasses", "datetime", "decimal",
    "difflib", "dis", "doctest", "email", "enum", "errno", "faulthandler", "fnmatch", "fractions", "ftplib",
    "functools", "gc", "getopt", "getpass", "gettext", "glob", "graphlib", "gzip", "hashlib", "heapq",
    "hmac", "html", "http", "imaplib", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "linecache", "locale", "logging", "lzma", "math", "mimetypes", "msvcrt", "multiprocessing",
    "netrc", "numbers", "operator", "optparse", "os", "pathlib", "pdb", "pickle", "pkgutil", "platform",
    "plistlib", "poplib", "pprint", "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "runpy", "sched", "secrets", "select", "selectors", "shlex", "shutil", "signal", "site", "smtplib",
    "socket", "socketserver", "sqlite3", "ssl", "stat", "statistics", "string", "struct", "subprocess",
    "sys", "sysconfig", "tarfile", "telnetlib", "tempfile", "textwrap", "threading", "time", "timeit",
    "tkinter", "token", "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty", "types",
    "typing", "unicodedata", "unittest", "urllib", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "wsgiref", "xml", "xmlrpc", "zipfile", "zlib", "zoneinfo",
}
STDLIB_NAMES = set(getattr(sys, "stdlib_module_names", ())) or STDLIB_FALLBACK
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".zip", ".gz", ".pyc", ".db", ".sqlite",
                   ".exe", ".dll", ".pdf", ".bin"}
SKIP_DIRS = IGNORED_DIRS | HIDDEN_DIRS | {".benchmark"}
MATCH_CASE = getattr(ast, "match_case", None)


def norm_path(p: str) -> str:
    p = (p or "").strip().strip("`'\"").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def walk_files(base: Path, skip: set[str] = SKIP_DIRS):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def is_test_path(rel: str) -> bool:
    parts = rel.lower().split("/")
    name = parts[-1]
    return (any(p in ("tests", "test") for p in parts[:-1]) or name.startswith("test_")
            or name.endswith("_test.py") or name in ("tests.py", "conftest.py"))


def source_root(bdir: Path) -> Path:
    p = bdir / "project"
    return p if p.is_dir() else bdir


def project_fingerprint(bdir: Path) -> str:
    h = hashlib.sha256()
    root = source_root(bdir)
    for p in walk_files(root):
        try:
            st = p.stat()
            h.update(f"{safe_rel(bdir, p)}|{st.st_size}|{st.st_mtime_ns}\n".encode())
        except OSError:
            pass
    return h.hexdigest()


def _walk_no_nested(node: ast.AST):
    stack = list(ast.iter_child_nodes(node))
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(n))


def complexity(fn: ast.AST) -> int:
    c = 1
    for n in _walk_no_nested(fn):
        if isinstance(n, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)):
            c += 1
        elif isinstance(n, ast.BoolOp):
            c += len(n.values) - 1
        elif isinstance(n, ast.comprehension):
            c += 1 + len(n.ifs)
        elif MATCH_CASE is not None and isinstance(n, MATCH_CASE):
            c += 1
    return c


_LOOPS = (ast.For, ast.AsyncFor, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def max_loop_depth(fn: ast.AST) -> int:
    best = 0

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal best
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            d = depth + 1 if isinstance(ch, _LOOPS) else depth
            best = max(best, d)
            visit(ch, d)

    visit(fn, 0)
    return best


def _func_record(qname: str, fn: Any) -> dict[str, Any]:
    a = fn.args
    allargs = list(getattr(a, "posonlyargs", [])) + list(a.args) + list(a.kwonlyargs)
    if a.vararg:
        allargs.append(a.vararg)
    if a.kwarg:
        allargs.append(a.kwarg)
    real = [x for x in allargs if x.arg not in ("self", "cls")]
    doc = ast.get_docstring(fn) is not None
    body = fn.body[1:] if doc and fn.body else fn.body

    def stubby(s: ast.stmt) -> bool:
        return (isinstance(s, ast.Pass)
                or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis)
                or (isinstance(s, ast.Raise) and "NotImplementedError" in ast.dump(s)))

    end = getattr(fn, "end_lineno", fn.lineno) or fn.lineno
    return {"name": qname, "line": fn.lineno, "length": end - fn.lineno + 1, "complexity": complexity(fn),
            "loop_depth": max_loop_depth(fn), "args": len(real), "doc": doc,
            "annotated": fn.returns is not None and all(x.annotation is not None for x in real),
            "stub": (not body) or all(stubby(s) for s in body),
            "public": not qname.split(".")[-1].startswith("_"),
            "_hash": hashlib.md5(ast.dump(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()
                     if end - fn.lineno + 1 >= 6 else ""}


def analyze_source_file(path: Path, rel: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    info: dict[str, Any] = {
        "path": rel, "lines": len(lines), "is_test": is_test_path(rel),
        "loc": sum(1 for l in lines if l.strip() and not l.strip().startswith("#")),
        "todo": len(re.findall(r"\b(?:TODO|FIXME|XXX|HACK)\b", text)),
    }
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError) as exc:
        info["parse_error"] = f"{type(exc).__name__}: {exc}"
        return info

    funcs: list[tuple[str, Any]] = []
    classes: list[tuple[str, ast.ClassDef]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append((prefix + ch.name, ch))
                visit(ch, prefix + ch.name + ".")
            elif isinstance(ch, ast.ClassDef):
                classes.append((prefix + ch.name, ch))
                visit(ch, prefix + ch.name + ".")
            else:
                visit(ch, prefix)

    visit(tree, "")
    info["module_doc"] = ast.get_docstring(tree) is not None
    info["functions"] = [_func_record(q, f) for q, f in funcs]
    info["classes"] = [{"name": q, "line": c.lineno, "doc": ast.get_docstring(c) is not None,
                        "methods": sum(isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) for x in c.body),
                        "public": not q.split(".")[-1].startswith("_")} for q, c in classes]

    cnt = dict(bare_except=0, broad_except=0, swallowed_except=0, raises=0, open_no_encoding=0,
               shell_true=0, eval_exec=0, os_system=0, input_calls=0, global_stmts=0,
               hardcoded_win_paths=0, atomic_replace=0)
    imports: list[list[Any]] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ExceptHandler):
            if n.type is None:
                cnt["bare_except"] += 1
            elif isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"):
                cnt["broad_except"] += 1
            if len(n.body) == 1 and isinstance(n.body[0], (ast.Pass, ast.Continue)):
                cnt["swallowed_except"] += 1
        elif isinstance(n, ast.Raise):
            cnt["raises"] += 1
        elif isinstance(n, ast.Global):
            cnt["global_stmts"] += 1
        elif isinstance(n, ast.Import):
            imports.append([None, 0, [a.name for a in n.names]])
        elif isinstance(n, ast.ImportFrom):
            imports.append([n.module or "", n.level or 0, [a.name for a in n.names]])
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                if f.id == "open":
                    kws = {k.arg for k in n.keywords}
                    mode = n.args[1].value if len(n.args) > 1 and isinstance(n.args[1], ast.Constant) else None
                    for k in n.keywords:
                        if k.arg == "mode" and isinstance(k.value, ast.Constant):
                            mode = k.value.value
                    if "encoding" not in kws and not (isinstance(mode, str) and "b" in mode):
                        cnt["open_no_encoding"] += 1
                elif f.id in ("eval", "exec"):
                    cnt["eval_exec"] += 1
                elif f.id == "input":
                    cnt["input_calls"] += 1
            elif isinstance(f, ast.Attribute):
                if f.attr == "system" and isinstance(f.value, ast.Name) and f.value.id == "os":
                    cnt["os_system"] += 1
                if f.attr in ("replace", "rename") and len(n.args) == 1 and not n.keywords:
                    cnt["atomic_replace"] += 1
                if f.attr == "replace" and isinstance(f.value, ast.Name) and f.value.id == "os":
                    cnt["atomic_replace"] += 1
            for k in n.keywords:
                if k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True:
                    cnt["shell_true"] += 1
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            if re.search(r"(?<![A-Za-z])[A-Za-z]:\\", n.value):
                cnt["hardcoded_win_paths"] += 1
    info.update(cnt)
    info["imports"] = imports
    names = {(i[0] or "").split(".")[0] for i in imports if i[0]} | {
        x.split(".")[0] for i in imports if i[0] is None for x in i[2]}
    info["import_names"] = sorted(names)
    info["mutable_globals"] = sum(
        1 for s in tree.body if isinstance(s, ast.Assign) and isinstance(s.value, (ast.List, ast.Dict, ast.Set))
        and any(isinstance(t, ast.Name) and not t.id.isupper() for t in s.targets))
    info["main_guard"] = any(isinstance(s, ast.If) and "__name__" in ast.dump(s.test) for s in tree.body)
    info["uses_cli_lib"] = bool(names & {"argparse", "click", "typer", "optparse"})

    if info["is_test"]:
        t = dict(test_classes=0, test_methods=0, test_methods_no_assert=0, assert_total=0,
                 raises_checks=0, pytest_style=0)
        for q, c in classes:
            if any((isinstance(b, ast.Name) and b.id == "TestCase") or
                   (isinstance(b, ast.Attribute) and b.attr == "TestCase") for b in c.bases):
                t["test_classes"] += 1
                for m in c.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test"):
                        t["test_methods"] += 1
                        asserts = 0
                        for x in ast.walk(m):
                            if isinstance(x, ast.Assert):
                                asserts += 1
                            elif isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) \
                                    and (x.func.attr.startswith("assert") or x.func.attr == "fail"):
                                asserts += 1
                                if "Raises" in x.func.attr:
                                    t["raises_checks"] += 1
                        t["assert_total"] += asserts
                        if asserts == 0:
                            t["test_methods_no_assert"] += 1
        t["pytest_style"] = sum(1 for q, _ in funcs if "." not in q and q.startswith("test_"))
        t["uses_tempfile"] = "tempfile" in names
        t["uses_mock"] = bool(names & {"mock"}) or any(i[0] == "unittest.mock" or "mock" in i[2] for i in imports if i[0])
        t["uses_subprocess"] = "subprocess" in names
        info["tests"] = t
    return info


def _module_name(rel: str, import_root: str) -> tuple[str, bool]:
    r = rel[len(import_root) + 1:] if import_root and rel.startswith(import_root + "/") else rel
    r = r[:-3] if r.endswith(".py") else r
    parts = r.split("/")
    is_pkg = parts[-1] == "__init__"
    if is_pkg:
        parts = parts[:-1]
    return ".".join(p for p in parts if p), is_pkg


def _edges(mod: str, is_pkg: bool, imports: list[list[Any]], modules: set[str]) -> set[str]:
    out: set[str] = set()
    pkg = mod if is_pkg else mod.rpartition(".")[0]
    for module, level, names in imports:
        if module is None:                      # plain `import a.b`
            targets = [(n, []) for n in names]
        else:
            if level:
                base = pkg.split(".") if pkg else []
                if level - 1 > len(base):
                    continue
                base = base[:len(base) - (level - 1)]
                module = ".".join(base + ([module] if module else []))
            targets = [(module, names)]
        for target, nms in targets:
            cands = [target] if target in modules else []
            cands += [f"{target}.{n}".strip(".") for n in nms if f"{target}.{n}".strip(".") in modules]
            if not cands:
                parts = target.split(".")
                while parts:
                    t = ".".join(parts)
                    if t in modules:
                        cands.append(t)
                        break
                    parts.pop()
            out.update(c for c in cands if c != mod)
    return out


def _sccs(graph: dict[str, set[str]]) -> list[list[str]]:
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on: set[str] = set()
    res: list[list[str]] = []
    counter = [0]

    def strong(v: str) -> None:
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                res.append(sorted(comp))

    for v in list(graph):
        if v not in index:
            strong(v)
    return res


def analyze_project(bdir: Path) -> dict[str, Any]:
    root = source_root(bdir)
    files: dict[str, dict[str, Any]] = {}
    for p in walk_files(root):
        if p.suffix == ".py":
            try:
                files[safe_rel(bdir, p)] = analyze_source_file(p, safe_rel(bdir, p))
            except Exception as exc:
                files[safe_rel(bdir, p)] = {"path": safe_rel(bdir, p), "parse_error": f"analyzer: {exc}",
                                            "is_test": False, "loc": 0}
    src = {k: v for k, v in files.items() if not v.get("is_test")}
    tst = {k: v for k, v in files.items() if v.get("is_test")}
    rel_root = safe_rel(bdir, root) if root != bdir else ""
    import_root = rel_root + "/src" if any(k.startswith(rel_root + "/src/") for k in src) else rel_root
    modules: dict[str, tuple[str, bool]] = {}
    for k in files:
        if "parse_error" not in files[k]:
            m, pkg = _module_name(k, import_root)
            if m:
                modules[k] = (m, pkg)
    mod_set = {m for m, _ in modules.values()}
    tops = {m.split(".")[0] for m, _ in modules.values()}
    graph: dict[str, set[str]] = {}
    tested: set[str] = set()
    for k, (m, pkg) in modules.items():
        e = _edges(m, pkg, files[k].get("imports", []), mod_set)
        if k in src:
            graph[m] = {x for x in e if x in {mm for kk, (mm, _) in modules.items() if kk in src}}
        else:
            tested |= e
    fan_in: dict[str, int] = {m: 0 for m in graph}
    for m, es in graph.items():
        for x in es:
            fan_in[x] = fan_in.get(x, 0) + 1
    cycles = _sccs(graph)
    pkg_mods = {m for k, (m, is_pkg) in modules.items() if is_pkg}

    def third(group: dict[str, dict[str, Any]]) -> list[str]:
        out = set()
        for v in group.values():
            for n in v.get("import_names", []):
                if n and n not in STDLIB_NAMES and n not in tops and n != "__future__":
                    out.add(n)
        return sorted(out)

    fn_all = [(k, f) for k, v in src.items() for f in v.get("functions", [])]
    pub_f = [f for _, f in fn_all if f["public"]]
    pub_c = [c for v in src.values() for c in v.get("classes", []) if c["public"]]
    lens = [f["length"] for _, f in fn_all]
    ccs = [f["complexity"] for _, f in fn_all]
    pct = lambda a, b: round(100.0 * a / b, 1) if b else None
    tsum = lambda key: sum(v.get("tests", {}).get(key, 0) for v in tst.values())
    groups: dict[str, list[str]] = {}
    for k, f in fn_all:
        if f["_hash"]:
            groups.setdefault(f["_hash"], []).append(f"{k}::{f['name']}")
    dups = sorted((g for g in groups.values() if len(g) > 1), key=len, reverse=True)[:5]
    for v in files.values():
        for f in v.get("functions", []):
            f.pop("_hash", None)

    readme = next((p for p in sorted(root.glob("*")) if p.is_file() and p.name.lower().startswith("readme")), None)
    docs: dict[str, Any] = {"readme": None}
    if readme:
        t = readme.read_text(encoding="utf-8", errors="replace")
        docs["readme"] = {"path": safe_rel(bdir, readme), "chars": len(t),
                          "headings": len(re.findall(r"^#{1,6}\s", t, re.M)),
                          "code_blocks": t.count("```") // 2,
                          "mentions_usage": bool(re.search(r"usage|example|использован|пример", t, re.I)),
                          "mentions_install": bool(re.search(r"install|setup|установ", t, re.I)),
                          "mentions_tests": bool(re.search(r"unittest|pytest|tests?\b|тест", t, re.I))}
    present = {n: (root / n).exists() for n in ("requirements.txt", "pyproject.toml", "setup.py", "setup.cfg")}
    present["__main__.py"] = any(k.endswith("__main__.py") for k in src)

    totals = {
        "py_files": len(files), "src_files": len(src), "test_files": len(tst),
        "src_loc": sum(v.get("loc", 0) for v in src.values()), "test_loc": sum(v.get("loc", 0) for v in tst.values()),
        "packages": sum(1 for k in src if k.endswith("__init__.py")),
        "max_dir_depth": max((k.count("/") for k in src), default=0),
        "functions": len(fn_all), "classes": sum(len(v.get("classes", [])) for v in src.values()),
        "avg_func_len": round(sum(lens) / len(lens), 1) if lens else 0, "max_func_len": max(lens, default=0),
        "avg_complexity": round(sum(ccs) / len(ccs), 2) if ccs else 0, "max_complexity": max(ccs, default=0),
        "funcs_cc_gt10": sum(1 for c in ccs if c > 10), "funcs_len_gt50": sum(1 for n in lens if n > 50),
        "funcs_loop_depth_ge3": sum(1 for _, f in fn_all if f["loop_depth"] >= 3),
        "stub_functions": sum(1 for _, f in fn_all if f["stub"]),
        "docstring_pct_public": pct(sum(f["doc"] for f in pub_f) + sum(c["doc"] for c in pub_c),
                                    len(pub_f) + len(pub_c)),
        "annotation_pct_public": pct(sum(f["annotated"] for f in pub_f), len(pub_f)),
        "todo_markers": sum(v.get("todo", 0) for v in src.values()),
        "bare_except": sum(v.get("bare_except", 0) for v in src.values()),
        "broad_except": sum(v.get("broad_except", 0) for v in src.values()),
        "swallowed_except": sum(v.get("swallowed_except", 0) for v in src.values()),
        "raises": sum(v.get("raises", 0) for v in src.values()),
        "open_without_encoding": sum(v.get("open_no_encoding", 0) for v in src.values()),
        "atomic_replace_calls": sum(v.get("atomic_replace", 0) for v in src.values()),
        "mutable_module_globals": sum(v.get("mutable_globals", 0) for v in src.values()),
        "global_statements": sum(v.get("global_stmts", 0) for v in src.values()),
        "eval_exec": sum(v.get("eval_exec", 0) for v in src.values()),
        "shell_true": sum(v.get("shell_true", 0) for v in src.values()),
        "os_system": sum(v.get("os_system", 0) for v in src.values()),
        "input_calls": sum(v.get("input_calls", 0) for v in src.values()),
        "hardcoded_windows_paths": sum(v.get("hardcoded_win_paths", 0) for v in src.values()),
        "uses_cli_lib": any(v.get("uses_cli_lib") for v in src.values()),
        "main_guard_files": sum(1 for v in src.values() if v.get("main_guard")),
        "third_party_src": third(src), "third_party_tests": [n for n in third(tst) if n != "unittest"],
        "import_cycles": cycles,
        "top_fan_in": sorted(fan_in.items(), key=lambda kv: -kv[1])[:4],
        "top_fan_out": sorted(((m, len(e)) for m, e in graph.items()), key=lambda kv: -kv[1])[:4],
        "modules_not_imported_by_tests": sorted(
            m for m in graph if m not in tested and m not in pkg_mods and not m.endswith("__main__")),
        "test_classes": tsum("test_classes"), "test_methods": tsum("test_methods"),
        "tests_without_assert": tsum("test_methods_no_assert"), "assert_total": tsum("assert_total"),
        "negative_tests_assertRaises": tsum("raises_checks"),
        "pytest_style_functions_not_run_by_unittest": tsum("pytest_style"),
        "tests_use_tempfile": any(v.get("tests", {}).get("uses_tempfile") for v in tst.values()),
        "tests_use_subprocess_cli": any(v.get("tests", {}).get("uses_subprocess") for v in tst.values()),
        "tests_use_mock": any(v.get("tests", {}).get("uses_mock") for v in tst.values()),
    }
    totals["avg_asserts_per_test"] = round(totals["assert_total"] / totals["test_methods"], 2) \
        if totals["test_methods"] else 0
    totals["test_to_src_loc_ratio"] = round(totals["test_loc"] / totals["src_loc"], 2) if totals["src_loc"] else 0
    top_cx = sorted(fn_all, key=lambda kf: -kf[1]["complexity"])[:6]
    top_len = sorted(fn_all, key=lambda kf: -kf[1]["length"])[:5]
    big_files = sorted(src.items(), key=lambda kv: -kv[1].get("loc", 0))[:5]
    st = {
        "root": safe_rel(bdir, root) if root != bdir else ".", "empty": not src,
        "syntax_errors": [{"path": k, "error": v["parse_error"]} for k, v in files.items() if "parse_error" in v],
        "totals": totals, "docs": docs, "config_files": present, "duplicate_function_groups": dups,
        "most_complex": [{"path": k, "function": f["name"], "line": f["line"], "complexity": f["complexity"],
                          "length": f["length"]} for k, f in top_cx],
        "longest_functions": [{"path": k, "function": f["name"], "line": f["line"], "length": f["length"]}
                              for k, f in top_len],
        "largest_files": [{"path": k, "loc": v.get("loc")} for k, v in big_files],
        "import_graph": {m: sorted(e) for m, e in graph.items()},
        "files": files,
    }
    return st


def static_digest(st: dict[str, Any]) -> dict[str, Any]:
    t = dict(st["totals"])
    for big in ("import_graph",):
        pass
    return {"root": st["root"], "syntax_errors": st["syntax_errors"], "totals": t, "docs": st["docs"],
            "config_files": st["config_files"], "duplicate_function_groups": st["duplicate_function_groups"],
            "most_complex": st["most_complex"], "longest_functions": st["longest_functions"],
            "largest_files": st["largest_files"], "import_graph": st["import_graph"]}


# ==========================================================================
# Running the generated project's tests / probes (disposable copy)
# ==========================================================================
def copy_project(src: Path, dest: Path) -> None:
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*SKIP_DIRS))


def _dec(b: Any) -> str:
    return b.decode("utf-8", errors="replace") if isinstance(b, bytes) else str(b or "")


def parse_unittest_output(err: str) -> dict[str, Any]:
    m = re.search(r"^Ran (\d+) tests? in.*$", err, re.M)
    res: dict[str, Any] = {"tests_run": int(m.group(1)) if m else 0, "failures": 0, "errors": 0, "skipped": 0}
    status = re.findall(r"^(OK|FAILED)(?: \(([^)]*)\))?\s*$", err, re.M)
    res["ok"] = bool(status and status[-1][0] == "OK" and res["tests_run"] > 0)
    if status and status[-1][1]:
        for k, v in re.findall(r"(failures|errors|skipped)=(\d+)", status[-1][1]):
            res[k] = int(v)
    res["summary"] = (m.group(0) if m else "no 'Ran N tests' line") + (
        f" | {status[-1][0]}" if status else "")
    return res


def run_project_tests(root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    use_cov = COVERAGE_ENABLED and importlib.util.find_spec("coverage") is not None
    tmp = Path(tempfile.mkdtemp(prefix="benchmark_audit_"))
    res: dict[str, Any] = {}
    try:
        work = tmp / "project"
        copy_project(root, work)
        env = os.environ.copy()
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
        def attempt(discover_args: list[str]) -> tuple[list[str], str, str, Optional[int], bool]:
            cmd = ([sys.executable, "-m", "coverage", "run", "--branch", "--source", ".", "-m", "unittest"]
                   if use_cov else [sys.executable, "-m", "unittest"]) + discover_args
            try:
                cp = subprocess.run(cmd, cwd=work, capture_output=True, stdin=subprocess.DEVNULL,
                                    timeout=UNITTEST_TIMEOUT_SECONDS, env=env, shell=False)
                return cmd, _dec(cp.stdout), _dec(cp.stderr), cp.returncode, False
            except subprocess.TimeoutExpired as exc:
                return cmd, _dec(exc.stdout), _dec(exc.stderr), None, True

        cmd, out, err, code, timed_out = attempt(["discover", "-v"])
        explicit_dir = False
        if not timed_out and parse_unittest_output(err)["tests_run"] == 0 and (work / "tests").is_dir():
            # plain discovery skips folders without __init__.py: retry the way a developer would
            cmd, out, err, code, timed_out = attempt(["discover", "-s", "tests", "-v"])
            explicit_dir = True
        res = {"command": " ".join(cmd), "exit_code": code, "timed_out": timed_out,
               "needed_explicit_start_dir": explicit_dir,
               "timeout_seconds": UNITTEST_TIMEOUT_SECONDS, **parse_unittest_output(err),
               "stdout_tail": out[-2500:], "stderr_tail": err[-7000:],
               "coverage_percent": None, "low_coverage_files": [], "coverage_available": use_cov}
        if use_cov and not timed_out:
            try:
                subprocess.run([sys.executable, "-m", "coverage", "json", "-o", "cov.json"], cwd=work,
                               capture_output=True, stdin=subprocess.DEVNULL, timeout=60, env=env)
                cov = json.loads((work / "cov.json").read_text(encoding="utf-8"))
                cov_files = {norm_path(k): v["summary"] for k, v in cov.get("files", {}).items()
                             if not is_test_path(norm_path(k))}
                n = sum(v.get("num_statements", 0) for v in cov_files.values())
                c = sum(v.get("covered_lines", 0) for v in cov_files.values())
                res["coverage_percent"] = round(100.0 * c / n, 1) if n else None
                res["low_coverage_files"] = sorted(
                    ({"path": k, "percent": round(v.get("percent_covered", 0), 1)} for k, v in cov_files.items()
                     if v.get("percent_covered", 100) < 60), key=lambda x: x["percent"])[:6]
            except Exception as exc:
                res["coverage_error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        res = {"error": f"{type(exc).__name__}: {exc}", "tests_run": 0, "ok": False}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    res["duration_seconds"] = round(time.perf_counter() - started, 2)
    return res


def run_probe_code(root: Path, code: str, timeout: int = PROBE_TIMEOUT_SECONDS) -> dict[str, Any]:
    started = time.perf_counter()
    tmp = Path(tempfile.mkdtemp(prefix="benchmark_probe_"))
    try:
        work = tmp / "project"
        copy_project(root, work)
        (work / "_probe.py").write_text(code, encoding="utf-8")
        env = os.environ.copy()
        env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
        timed_out, rc = False, None
        try:
            cp = subprocess.run([sys.executable, "_probe.py"], cwd=work, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=timeout, env=env, shell=False)
            out, err, rc = _dec(cp.stdout), _dec(cp.stderr), cp.returncode
        except subprocess.TimeoutExpired as exc:
            out, err, timed_out = _dec(exc.stdout), _dec(exc.stderr), True
        return {"exit_code": rc, "timed_out": timed_out, "timeout_seconds": timeout,
                "duration_seconds": round(time.perf_counter() - started, 2),
                "stdout_tail": out[-5000:], "stderr_tail": err[-3000:]}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ==========================================================================
# Read-only inspection tools for auditors
# ==========================================================================
def outline(value: Any, depth: int = 2) -> Any:
    if depth <= 0:
        return f"<{type(value).__name__}>"
    if isinstance(value, dict):
        return {k: outline(v, depth - 1) for k, v in list(value.items())[:60]}
    if isinstance(value, list):
        return {"__list__": len(value), "first": outline(value[0], depth - 1) if value else None}
    if isinstance(value, str):
        return f"<str {len(value)} chars>"
    return value


class Inspector:
    def __init__(self, root: Path, static: Optional[dict[str, Any]] = None,
                 unit: Optional[dict[str, Any]] = None):
        self.root = root.resolve()
        self.static = static
        self.unit = unit
        self.probes_run = 0
        self._text: Optional[tuple[str, float, str]] = None

    def _path(self, rel: str) -> Path:
        p = resolve_inside(self.root, rel)
        if set(p.relative_to(self.root).parts) & HIDDEN_DIRS:
            raise PermissionError("This path is not part of the audited evidence")
        return p

    def _canon(self, p: Path) -> str:
        return safe_rel(self.root, p) if p != self.root else "."

    def _walk(self, base: Path):
        return walk_files(base, IGNORED_DIRS | HIDDEN_DIRS)

    def _load(self, p: Path) -> str:
        key = (str(p), p.stat().st_mtime)
        if self._text and self._text[:2] == key:
            return self._text[2]
        with p.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_TEXT_LOAD_CHARS)
        self._text = (key[0], key[1], text)
        return text

    def tree_lines(self, rel: str = "", max_entries: int = MAX_TREE_ENTRIES) -> tuple[list[str], bool]:
        base = self._path(rel)
        lines: list[str] = []
        truncated = False
        for p in self._walk(base):
            if len(lines) >= max_entries:
                truncated = True
                break
            try:
                lines.append(f"{self._canon(p)}  ({p.stat().st_size} B)")
            except OSError:
                pass
        return lines, truncated

    def tree(self, rel: str = "", max_entries: int = MAX_TREE_ENTRIES) -> dict[str, Any]:
        base = self._path(rel)
        if not base.exists():
            return {"error": "not_found", "path": rel}
        if not base.is_dir():
            return {"error": "not_directory", "path": rel}
        n = max(1, min(int(max_entries or MAX_TREE_ENTRIES), MAX_TREE_ENTRIES))
        lines, truncated = self.tree_lines(rel, n)
        return {"requested": rel or ".", "files": lines, "truncated": truncated}

    def read(self, rel: str, offset: int = 0, max_chars: int = MAX_READ_CHARS_PER_CALL) -> dict[str, Any]:
        p = self._path(rel)
        if not p.exists():
            return {"error": "not_found", "path": rel}
        if not p.is_file():
            return {"error": "not_file", "path": rel}
        if p.suffix.lower() in BINARY_SUFFIXES:
            return {"error": "binary_file", "path": rel}
        text = self._load(p)
        offset = max(0, int(offset or 0))
        limit = min(max(1, int(max_chars or MAX_READ_CHARS_PER_CALL)), MAX_READ_CHARS_PER_CALL)
        data = text[offset:offset + limit]
        end = offset + len(data)
        res: dict[str, Any] = {"path": self._canon(p), "offset": offset, "total_chars": len(text),
                               "chars_returned": len(data), "content": data, "has_more": end < len(text)}
        if end < len(text):
            res["next_offset"] = end
        return res

    def read_lines(self, rel: str, start: int = 1, end: int = 200) -> dict[str, Any]:
        p = self._path(rel)
        if not p.is_file():
            return {"error": "not_found_or_not_file", "path": rel}
        if p.suffix.lower() in BINARY_SUFFIXES:
            return {"error": "binary_file", "path": rel}
        lines = self._load(p).splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), max(start, int(end or start + 199)))
        out, used = [], 0
        for n in range(start, end + 1):
            row = f"{n}: {lines[n - 1][:1500]}"
            used += len(row) + 1
            if used > MAX_READ_CHARS_PER_CALL:
                end = n - 1
                break
            out.append(row)
        return {"path": self._canon(p), "start": start, "end": end, "total_lines": len(lines),
                "content": "\n".join(out), "has_more": end < len(lines)}

    def read_json(self, rel: str, key: str = "") -> dict[str, Any]:
        try:
            p = self._path(rel)
            if not p.is_file():
                return {"error": "not_found_or_not_file", "path": rel}
            value: Any = json.loads(self._load(p))
            for part in [x for x in re.split(r"[./]", key or "") if x != ""]:
                value = value[int(part)] if isinstance(value, list) else value[part]
        except Exception as exc:
            return {"path": rel, "error": f"{type(exc).__name__}: {exc}"}
        text = jcompact(value)
        if len(text) <= MAX_READ_CHARS_PER_CALL:
            return {"path": self._canon(p), "key": key, "json": value}
        return {"path": self._canon(p), "key": key, "too_large_chars": len(text), "outline": outline(value),
                "hint": "Call read_json again with `key` (dotted path) to open one part."}

    def search(self, pattern: str, rel: str = "", max_results: int = MAX_SEARCH_RESULTS) -> dict[str, Any]:
        base = self._path(rel)
        if not base.exists():
            return {"error": "not_found", "path": rel}
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            rx = re.compile(re.escape(pattern), re.IGNORECASE)
        limit = max(1, min(int(max_results or MAX_SEARCH_RESULTS), MAX_SEARCH_RESULTS))
        files = [base] if base.is_file() else self._walk(base)
        matches, scanned = [], 0
        for p in files:
            if len(matches) >= limit:
                break
            if p.suffix.lower() in BINARY_SUFFIXES:
                continue
            try:
                if p.stat().st_size > MAX_FILE_SIZE_FOR_DIRECT_READ:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            scanned += 1
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    matches.append({"path": self._canon(p), "line": n, "text": line[:300]})
                    if len(matches) >= limit:
                        break
        return {"pattern": pattern, "matches": matches, "scanned_files": scanned,
                "truncated": len(matches) >= limit}

    def file_info(self, rel: str) -> dict[str, Any]:
        p = self._path(rel)
        if not p.exists():
            return {"error": "not_found", "path": rel}
        st = p.stat()
        return {"path": self._canon(p), "type": "directory" if p.is_dir() else "file", "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()}

    def file_metrics(self, rel: str) -> dict[str, Any]:
        """Per-function facts from the static analysis (line numbers, size, complexity)."""
        if not self.static:
            return {"error": "static analysis not available"}
        key = self._canon(self._path(rel))
        f = (self.static.get("files") or {}).get(key)
        if not f:
            return {"error": "not a python file known to the static analysis", "path": key}
        keep = ("name", "line", "length", "complexity", "loop_depth", "args", "doc", "annotated", "stub")
        return {"path": key, "loc": f.get("loc"), "is_test": f.get("is_test"), "parse_error": f.get("parse_error"),
                "imports": f.get("import_names"), "classes": f.get("classes"),
                "functions": [{k: fn[k] for k in keep} for fn in f.get("functions", [])]}

    def run_unittest(self) -> dict[str, Any]:
        if self.unit is None:
            self.unit = run_project_tests(source_root(self.root))
        return dict(self.unit, note="Precomputed once per project (disposable copy); identical for all reviewers.")

    def run_probe(self, code: str, timeout: int = PROBE_TIMEOUT_SECONDS) -> dict[str, Any]:
        if self.probes_run >= MAX_PROBES_PER_AUDIT:
            return {"error": f"probe budget exhausted ({MAX_PROBES_PER_AUDIT})"}
        if not str(code or "").strip():
            return {"error": "empty code"}
        self.probes_run += 1
        res = run_probe_code(source_root(self.root), str(code), max(5, min(int(timeout or 30), PROBE_TIMEOUT_SECONDS)))
        res["probe_id"] = self.probes_run
        res["cite_as"] = f"probe:{self.probes_run}"
        return res


def _int(args: dict[str, Any], key: str, default: int) -> int:
    try:
        return int(args.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def make_audit_executor(inspector: Inspector) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    def run(name: str, a: dict[str, Any]) -> dict[str, Any]:
        path = str(a.get("path", "") or "")
        if name == "list_tree":
            return inspector.tree(path, _int(a, "max_entries", MAX_TREE_ENTRIES))
        if name == "read_file":
            return inspector.read(path, _int(a, "offset", 0), _int(a, "max_chars", MAX_READ_CHARS_PER_CALL))
        if name == "read_lines":
            return inspector.read_lines(path, _int(a, "start", 1), _int(a, "end", 200))
        if name == "read_json":
            return inspector.read_json(path, str(a.get("key", "") or ""))
        if name == "search_text":
            return inspector.search(str(a.get("pattern", "")), path, _int(a, "max_results", MAX_SEARCH_RESULTS))
        if name == "file_info":
            return inspector.file_info(path)
        if name == "file_metrics":
            return inspector.file_metrics(path)
        if name == "run_unittest":
            return inspector.run_unittest()
        if name == "run_probe":
            return inspector.run_probe(str(a.get("code", "")), _int(a, "timeout", 30))
        return {"error": f"unknown tool {name!r}", "valid_tools": [t["function"]["name"] for t in AUDIT_TOOLS]}
    return run


def _tool(name: str, desc: str, props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


_S, _I = {"type": "string"}, {"type": "integer"}
AUDIT_TOOLS = [
    _tool("list_tree", "List files under the audited result directory (relative path).", {"path": _S, "max_entries": _I}, []),
    _tool("read_file", "Read a text file in character chunks. Use next_offset to continue.", {"path": _S, "offset": _I, "max_chars": _I}, ["path"]),
    _tool("read_lines", "Read a line range (1-based, inclusive) with line numbers. Best for source code and *.jsonl logs and for citing path:line.", {"path": _S, "start": _I, "end": _I}, ["path"]),
    _tool("read_json", "Read a JSON file; for big files returns an outline, then use `key` (dotted path).", {"path": _S, "key": _S}, ["path"]),
    _tool("search_text", "Regex search in a file or directory.", {"pattern": _S, "path": _S, "max_results": _I}, ["pattern"]),
    _tool("file_info", "File metadata.", {"path": _S}, ["path"]),
    _tool("file_metrics", "Static per-function facts of one .py file (line, length, cyclomatic complexity, loop depth, docstring/annotations, stubs).", {"path": _S}, ["path"]),
    _tool("run_unittest", "Result of `unittest discover` in a disposable copy (precomputed, includes coverage if available).", {}, []),
    _tool("run_probe", "Run YOUR OWN short Python script in a disposable copy of the project (cwd = project root, stdin closed, timeout). Use it to test behaviour empirically: import the package, create thousands of records and time operations, feed corrupted/edge-case input, call the CLI via subprocess. Cite the result as probe:N.", {"code": _S, "timeout": _I}, ["code"]),
]


# ==========================================================================
# Requirements checklist, rubric and prompts
# ==========================================================================
def load_requirements(task: str) -> list[dict[str, str]]:
    f = CONFIG_DIR / "requirements.txt"
    items: list[str] = []
    if f.is_file():
        items = [l.strip() for l in read_text(f).splitlines() if l.strip() and not l.strip().startswith("#")]
    else:
        for line in task.splitlines():
            m = re.match(r"^\s*(?:[-*•–]|\d+[.)]|\[[ xX]\])\s+(.+\S)\s*$", line)
            if m:
                items.append(m.group(1))
        if len(items) < 3:
            items = []
            for s in re.split(r"(?<=[.!?])\s+|\n+", task):
                s = s.strip()
                if 15 <= len(s) <= 400 and re.search(
                        r"\b(must|should|shall|support|implement|require|include|provide|allow|need|create|add)\b", s, re.I):
                    items.append(s)
        if not items:
            items = ["The task as a whole is implemented completely and correctly"]
    return [{"id": f"R{i}", "text": clip(t, 300)} for i, t in enumerate(items[:MAX_REQUIREMENTS], 1)]


SCALE_TEXT = (
    "SCALE (apply strictly): 0 = absent or broken; 1 = poor; 2 = weak, major gaps; 3 = acceptable, noticeable gaps; "
    "4 = good, only minor issues; 5 = exemplary (rare). The typical result of a small local model deserves 2-3. "
    "A 4 or 5 requires proof you opened or measured yourself. A 5 needs at least two evidence references. "
    "A dimension you could not verify must be scored <= 2. Never raise a score because the agent's own summary claims success."
)

DIMENSIONS: dict[str, dict[str, Any]] = {
    "architecture_structure": {"label": "Architecture & structure", "weight": 0.15, "anchors": (
        "Package/module layout; separation of concerns (CLI parsing vs domain model vs persistence vs output formatting); "
        "cohesion; import graph (static: import_cycles, fan-in/out); clear entry point; business logic leaking into CLI; god-modules. "
        "1 = one tangled file/broken layout; 2 = split exists but concerns are mixed; 3 = sensible modules, minor leakage; "
        "4 = clean layers, no cycles, obvious extension points; 5 = exemplary, could be handed to a team as-is.")},
    "extensibility_scalability": {"label": "Extensibility & scalability", "weight": 0.15, "anchors": (
        "Effort to add a field/command/storage backend (how many places change); abstractions around persistence; data structures "
        "and algorithmic cost at 10k-100k records (full-file rewrite per operation? linear scans? repeated sorting? load-everything "
        "per command?); CSV streaming vs loading; ID generation safety; safe concurrent writes. PREFER MEASUREMENT: use run_probe to "
        "time operations on thousands of records. 1 = hard-wired, breaks on moderate data; 2 = small data only, no seams; "
        "3 = fine to ~10k records, some seams; 4 = good seams and sound complexity; 5 = exemplary and demonstrated by a probe.")},
    "code_quality_maintainability": {"label": "Code quality & maintainability", "weight": 0.15, "anchors": (
        "Naming, function size and complexity (static: cc>10, >50 lines, loop depth), duplication, dead code/stubs/TODOs, magic "
        "values, type hints, docstrings, idiomatic Python, consistent style. 1 = unreadable/broken; 2 = works but messy; "
        "3 = readable with notable smells; 4 = clean, small functions, typed/documented; 5 = exemplary.")},
    "robustness_error_handling": {"label": "Robustness & error handling", "weight": 0.10, "anchors": (
        "Input validation; corrupted/missing storage file; atomic writes; explicit encodings; CSV edge cases (quotes, unicode, bad "
        "rows, duplicate ids); clear messages and exit codes; no bare/swallowed excepts; no tracebacks on bad input. Verify with "
        "run_probe. 1 = crashes on ordinary bad input; 2 = handles only the happy path; 3 = main failures handled; "
        "4 = thorough, atomic, tested; 5 = exemplary.")},
    "testing_quality": {"label": "Testing quality", "weight": 0.10, "anchors": (
        "Tests really executed (unittest result is provided), meaningful assertions (static: tests_without_assert, negative tests), "
        "isolation (tempdirs), coverage % if available, edge cases, mapping to requirements, end-to-end CLI test. pytest-style tests "
        "that unittest discover cannot run do not count. Failing or not-run tests: <= 2. 1 = none/all broken; 2 = few shallow tests; "
        "3 = decent happy-path coverage; 4 = broad, edge cases, isolated; 5 = exemplary.")},
    "documentation_devx": {"label": "Documentation & developer experience", "weight": 0.05, "anchors": (
        "README accuracy (verify that documented commands really work), install/run/test instructions, usage examples, --help quality, "
        "docstrings, entry points (__main__.py), Windows notes. 1 = none; 2 = stub README; 3 = usable; 4 = accurate and complete; 5 = exemplary.")},
    "constraint_compliance": {"label": "Constraint compliance", "weight": 0.05, "anchors": (
        "Respects the task constraints: stdlib only (static third_party_src must be empty), no forbidden external services, Windows "
        "compatibility (paths, encodings, no POSIX-only calls), no eval/exec/shell=True, no blocking input(), nothing written outside "
        "the project. 1 = major violation; 3 = minor violations; 5 = fully compliant.")},
}
COMPLETENESS_WEIGHT = 0.25
DIM_KEYS = list(DIMENSIONS)
WEIGHTS = {"completeness": COMPLETENESS_WEIGHT, **{k: v["weight"] for k, v in DIMENSIONS.items()}}
STATUS_CREDIT = {"PASS": 1.0, "PARTIAL": 0.5}          # when the evidence is valid
STATUS_CREDIT_UNSUPPORTED = {"PASS": 0.4, "PARTIAL": 0.2}
TERMINATIONS = ["genuine_model_success", "genuine_model_failure", "infrastructure_failure", "benchmark_limit",
                "user_interrupted", "mixed_model_and_infrastructure", "insufficient_evidence"]

BASE_SYSTEM = r"""
You are an independent senior software-engineering auditor. You review ONE project generated by an autonomous
coding agent the way a tech lead does a due-diligence review before adopting the code base: completeness against the
requirements, architecture and structure, scalability and extensibility, maintainability, robustness, tests,
documentation and compliance with the task constraints. You also notice how the agent behaved, but agent behaviour is
reported separately and does NOT change the project dimensions.

Rules:
- Evidence only. Every claim must point to something you opened or measured: `path:line` (use read_lines so you know the
  line numbers), `static:<field>`, `unittest`, or `probe:N`. Claims without evidence are discarded by a script.
- Do not trust REPORT.md, report.json status or the agent's final message. SUCCESS is not proof of quality.
- Static metrics and the unittest result in the prompt were computed by scripts: they are facts. Interpret them; do not argue with them.
- Infrastructure problems (load errors, timeouts, tool limits) are not model failures; classify them separately.
- Judge the engineering, not just whether it runs: look at how the code is organised and what it would take to extend it.
- Do not read everything. Open the core modules, one or two test files, the README, then test behaviour with run_probe.
- Never access files outside the assigned result directory. Never modify anything. Never fabricate results.
""".strip()

PROTOCOL_RULES = r"""

WORKING PROTOCOL (mandatory):
- The run summary, requirement checklist, static metrics, test result and file list are already provided. Do not re-read them.
- Every identical repeated tool call is refused. Tool output is truncated when large. You have a tool budget and a time limit.
- To finish, reply with the audit (short Markdown) followed by ONE fenced ```json block in the required schema,
  as a normal message WITHOUT any tool call. Do not announce that you will write it - write it.
- If a message tells you what to fix, send ONLY the corrected part (e.g. the corrected JSON block), not the whole audit again.
""".rstrip()

AGG_SYSTEM = r"""
You are the final analyst of a local LLM coding-agent benchmark. You receive a machine-generated data set: scores per
project were ALREADY computed by a script from several independent reviewers' rubric answers (weighted medians), plus
static code metrics, test results and agent process statistics.

YOUR JOB IS INTERPRETATION ONLY. Write the commentary in Russian (keep model names, CRUD/JSON/CLI, metric names in English).
Hard rules:
- Never compute, change, average or re-rank scores. Never output a ranking table; the script prints all tables.
  When you mention a number, copy it exactly from the data.
- Use only model names that occur in the data. Each benchmark appears exactly once. Do not invent facts, tests or numbers.
- Reviewers are ANALYST_### only; never guess which model they are.
- If data is thin or reviewers disagree, say so plainly and name the evidence (critical_issues / weaknesses given in the data).

Sections (Markdown, in this order):
1. Общий вывод
2. Кто лучше для каких задач (практичность; архитектура и масштабируемость; надёжность и эффективность агента)
3. Что отличает лидеров от аутсайдеров (по метрикам структуры, тестам, ошибкам)
4. Нерейтингуемые и сомнительные результаты (инфраструктура, низкая уверенность, расхождения аналитиков)
5. Проблемы валидности бенчмарка и аудита
6. Рекомендации для следующего прогона (бенчмарк, параметры, выбор судей)

Reply with the commentary as a normal message. Do not call tools at the end.
""".strip()


def load_optional(path: Path) -> str:
    try:
        return read_text(path).strip() if path.is_file() else ""
    except OSError:
        return ""


def format_block(reqs: list[dict[str, str]]) -> str:
    dim_lines = ",\n".join(
        f'    "{k}": {{"score": 3, "evidence": ["<exact path:line you opened>", "<static:totals.FIELD or unittest or probe:N>"], '
        f'"rationale": "one sentence"}}' for k in DIM_KEYS)
    first = reqs[0]["id"] if reqs else "R1"
    last = reqs[-1]["id"] if reqs else "R1"
    return (
        "FINAL ANSWER FORMAT (strict):\n"
        "1) A concise audit in Markdown (<= 900 words): executive verdict; termination classification; what the architecture looks "
        "like and how it would scale/extend; code quality; tests; robustness; agent behaviour; strengths; weaknesses.\n"
        "2) Then exactly ONE fenced json block with this schema (valid JSON, no comments, no trailing commas):\n"
        "```json\n{\n"
        f'  "termination": "{" | ".join(TERMINATIONS)}",\n'
        '  "confidence": 70,\n'
        '  "requirements": [\n'
        f'    {{"id": "{first}", "status": "PASS", "evidence": ["<exact path:line you opened>"]}},\n'
        f'    "... one entry for EVERY id {first}..{last}; status = PASS | PARTIAL | FAIL | UNVERIFIED; FAIL needs no evidence ..."\n'
        "  ],\n"
        '  "dimensions": {\n' + dim_lines + "\n  },\n"
        '  "critical_issues": ["..."],\n  "strengths": ["..."],\n  "weaknesses": ["..."]\n}\n```\n'
        "Replace the placeholder entry in `requirements` with real entries. `score` is an integer 0-5. Evidence strings: exact "
        "paths as returned by the tools (you must have opened the file; the line must exist), optionally :line or :start-end; "
        "`static:<dotted field of the static metrics above, e.g. static:totals.max_complexity>`; `unittest`; `probe:N` "
        "(only probes you ran). Invalid references are discarded and lower the reviewer's weight.")


def rubric_block() -> str:
    parts = [SCALE_TEXT, ""]
    for k, d in DIMENSIONS.items():
        parts.append(f"* {k} ({d['label']}, weight {int(d['weight'] * 100)}%): {d['anchors']}")
    parts.append("* completeness is NOT scored by you: a script derives it from your requirement statuses "
                 "(PASS needs valid evidence to get full credit).")
    return "\n".join(parts)


# ==========================================================================
# Rubric parsing, evidence validation and per-audit scoring (pure functions)
# ==========================================================================
def extract_last_json(text: str) -> Optional[dict[str, Any]]:
    """Last JSON object containing "dimensions" (fenced or not); tolerant to prose around it."""
    dec = json.JSONDecoder()
    found: Optional[dict[str, Any]] = None
    pos = 0
    while True:
        i = text.find("{", pos)
        if i < 0:
            break
        try:
            obj, end = dec.raw_decode(text, i)
        except ValueError:
            pos = i + 1
            continue
        if isinstance(obj, dict) and "dimensions" in obj:
            found = obj
            pos = end
        else:
            pos = i + 1
    return found


class EvidenceChecker:
    def __init__(self, root: Path, seen: set[str], probes_run: int, unit_available: bool,
                 static: Optional[dict[str, Any]] = None):
        self.root = root
        self.static = static or {}
        self.seen = {norm_path(s) for s in seen}
        self.probes = probes_run
        self.unit = unit_available
        self._lines: dict[str, int] = {}

    def _nlines(self, p: Path) -> int:
        k = str(p)
        if k not in self._lines:
            try:
                self._lines[k] = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                self._lines[k] = 0
        return self._lines[k]

    def ok(self, ref: Any) -> bool:
        s = str(ref or "").strip().strip("`'\"")
        low = s.lower()
        if not s:
            return False
        if low.startswith("static:"):
            cur: Any = self.static          # must be a real field of the static digest, e.g. totals.max_complexity
            for part in s[7:].strip().split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return False
            return True
        if low == "unittest" or low.startswith("unittest:"):
            return self.unit
        if low.startswith("probe:"):
            try:
                return 1 <= int(low.split(":", 1)[1]) <= self.probes
            except ValueError:
                return False
        m = re.match(r"^(?P<p>.+?)(?::(?P<a>\d+)(?:-(?P<b>\d+))?)?$", norm_path(s))
        if not m:
            return False
        path = m.group("p")
        if path not in self.seen and path.lower() not in ("report.json", "verification.json"):
            return False
        try:
            p = resolve_inside(self.root, path)
        except PermissionError:
            return False
        if not p.is_file():
            return False
        if m.group("a"):
            n = self._nlines(p)
            hi = int(m.group("b") or m.group("a"))
            return 1 <= int(m.group("a")) <= n and hi <= n + 2
        return True


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def evaluate_audit(text: str, reqs: list[dict[str, str]], checker: EvidenceChecker,
                   static: dict[str, Any], unit: dict[str, Any], verification_failed: bool) -> dict[str, Any]:
    ev: dict[str, Any] = {"valid": False, "problems": [], "caps": [], "requirements": {}, "dimensions": {},
                          "termination": None, "confidence": None, "critical": [], "strengths": [],
                          "weaknesses": [], "claimed_overall": None, "evidence_total": 0, "evidence_valid": 0,
                          "evidence_valid_ratio": 0.0, "completeness_ratio": 0.0, "overall": None,
                          "invalid_refs": []}
    data = extract_last_json(text or "")
    if data is None:
        ev["problems"].append("No valid JSON block with the required schema was found. End the answer with ONE "
                              "fenced ```json block (valid JSON: double quotes, no comments, no trailing commas).")
        return ev
    ev["termination"] = data.get("termination") if data.get("termination") in TERMINATIONS else "insufficient_evidence"
    try:
        ev["confidence"] = max(0, min(100, int(float(data.get("confidence")))))
    except (TypeError, ValueError):
        ev["confidence"] = None
    for k, name in (("critical", "critical_issues"), ("strengths", "strengths"), ("weaknesses", "weaknesses")):
        ev[k] = [clip(str(x), 220) for x in _as_list(data.get(name))][:6]

    def check(refs: Any) -> tuple[int, int]:
        good = bad = 0
        for r in _as_list(refs):
            if checker.ok(r):
                good += 1
            else:
                bad += 1
                ev["invalid_refs"].append(str(r)[:120])
        return good, bad

    # requirements
    raw = data.get("requirements")
    table: dict[str, Any] = {}
    if isinstance(raw, dict):
        raw = [{"id": k, **(v if isinstance(v, dict) else {"status": v})} for k, v in raw.items()]
    for item in _as_list(raw):
        if isinstance(item, dict) and item.get("id"):
            table[str(item["id"]).strip().upper()] = item
    missing, credit_sum = [], 0.0
    for r in reqs:
        item = table.get(r["id"].upper())
        if not item:
            missing.append(r["id"])
            ev["requirements"][r["id"]] = {"status": "MISSING", "credit": 0.0, "valid_evidence": False}
            continue
        status = str(item.get("status", "")).strip().upper()
        status = status if status in ("PASS", "PARTIAL", "FAIL", "UNVERIFIED") else "UNVERIFIED"
        good, bad = check(item.get("evidence"))
        ev["evidence_total"] += good + bad
        ev["evidence_valid"] += good
        credit = (STATUS_CREDIT if good else STATUS_CREDIT_UNSUPPORTED).get(status, 0.0)
        credit_sum += credit
        ev["requirements"][r["id"]] = {"status": status, "credit": credit, "valid_evidence": bool(good)}
    if missing:
        ev["problems"].append(f"`requirements` lacks entries for: {', '.join(missing[:12])}"
                              f"{'...' if len(missing) > 12 else ''}. Send only the corrected json block with all ids.")
    ratio = credit_sum / len(reqs) if reqs else 0.0
    claimed_ratio = (sum(1.0 if it.get("status") == "PASS" else 0.5 if it.get("status") == "PARTIAL" else 0.0
                         for it in (v for v in ({"status": str(table[r["id"].upper()].get("status", "")).strip().upper()}
                                                if r["id"].upper() in table else {} for r in reqs)))
                     / len(reqs)) if reqs else 0.0

    # dimensions
    dims = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else {}
    absent = [k for k in DIM_KEYS if k not in dims]
    if absent:
        ev["problems"].append(f"`dimensions` lacks: {', '.join(absent)}.")
    for k in DIM_KEYS:
        d = dims.get(k)
        if not isinstance(d, dict):
            continue
        try:
            raw_score = max(0.0, min(5.0, float(d.get("score"))))
        except (TypeError, ValueError):
            ev["problems"].append(f"dimension {k}: `score` must be a number 0-5.")
            continue
        good, bad = check(d.get("evidence"))
        ev["evidence_total"] += good + bad
        ev["evidence_valid"] += good
        adj, notes = raw_score, []
        if good == 0 and adj > 2:
            adj, notes = 2.0, ["no valid evidence -> capped at 2"]
        if adj >= 5 and good < 2:
            adj, notes = 4.0, notes + ["score 5 needs >= 2 valid evidence refs -> capped at 4"]
        ev["dimensions"][k] = {"raw": raw_score, "score": adj, "evidence_valid": good, "evidence_invalid": bad,
                               "rationale": clip(str(d.get("rationale", "")), 240), "notes": notes}

    # deterministic caps from script facts
    tot = static.get("totals", {}) if static else {}
    def cap(key: str, limit: float, why: str) -> None:
        d = ev["dimensions"].get(key)
        if d and d["score"] > limit:
            d["score"] = limit
            d["notes"].append(why)
            ev["caps"].append(f"{key}<= {limit:g}: {why}")
    if static and static.get("empty"):
        for k in ev["dimensions"]:
            ev["dimensions"][k]["score"] = 0.0
        ratio = 0.0
        ev["caps"].append("no source files -> everything 0")
    else:
        if static and static.get("syntax_errors"):
            cap("robustness_error_handling", 1, "syntax errors in source")
            cap("code_quality_maintainability", 2, "syntax errors in source")
            cap("testing_quality", 2, "syntax errors in source")
        if unit is not None:
            if not unit.get("tests_run"):
                cap("testing_quality", 1, "unittest ran 0 tests")
            elif not unit.get("ok"):
                cap("testing_quality", 2, "unittest run failed/timed out")
        if tot.get("third_party_src"):
            cap("constraint_compliance", 1, f"third-party imports: {tot['third_party_src']}")
        if tot.get("eval_exec") or tot.get("shell_true") or tot.get("os_system"):
            cap("constraint_compliance", 3, "eval/exec/shell=True/os.system used")
        if verification_failed and ratio > 0.7:
            ratio = 0.7
            ev["caps"].append("completeness<=70%: benchmark's independent verification failed")
    ev["completeness_ratio"] = round(ratio, 4)
    ev["evidence_valid_ratio"] = round(ev["evidence_valid"] / ev["evidence_total"], 3) if ev["evidence_total"] else 0.0
    if ev["evidence_total"] and ev["evidence_valid_ratio"] < 0.4:
        sample = "; ".join(ev["invalid_refs"][:4])
        ev["problems"].append("Most evidence references are invalid (paths must be exactly as returned by the tools and "
                              f"you must have opened the file; lines must exist). Examples: {sample}")
    ev["valid"] = bool(not absent and len(ev["dimensions"]) == len(DIM_KEYS))
    if ev["valid"]:
        ev["claimed_overall"] = round(100.0 * (
            COMPLETENESS_WEIGHT * claimed_ratio +
            sum(DIMENSIONS[k]["weight"] * ev["dimensions"][k]["raw"] / 5.0 for k in DIM_KEYS)), 1)
        ev["overall"] = round(100.0 * (
            COMPLETENESS_WEIGHT * ratio +
            sum(DIMENSIONS[k]["weight"] * ev["dimensions"][k]["score"] / 5.0 for k in DIM_KEYS)), 1)
    return ev


def load_prompt(path: Path, default: str) -> str:
    try:
        if path.is_file():
            text = read_text(path)
            if text.strip():
                return text
    except OSError:
        pass
    return default


# ==========================================================================
# Discovery
# ==========================================================================
def discover_benchmark_dirs() -> list[Path]:
    if not RESULTS_DIR.exists():
        return []
    out = []
    for p in sorted(RESULTS_DIR.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_dir() or p.name.startswith((".", "_")) or "__previous_" in p.name:
            continue
        if any((p / f).exists() for f in ("report.json", "REPORT.md", "load_error.txt")):
            out.append(p)
    return out


def summary_for(path: Path) -> dict[str, Any]:
    rp = path / "report.json"
    if not rp.exists():
        return {"model_dir": path.name, "model": {"key": path.name}}
    try:
        d = json.loads(read_text(rp))
        return {"model_dir": path.name, **{k: d.get(k, {}) for k in (
            "model", "benchmark", "agent", "tokens", "project", "verification", "model_load")}}
    except Exception as exc:
        return {"model_dir": path.name, "error": str(exc), "model": {"key": path.name}}


def available_tool_models(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for m in catalog:
        key = str(m.get("key"))
        caps = m.get("capabilities") or {}
        if "embedding" in key.lower():
            continue
        if isinstance(caps, dict) and caps.get("trained_for_tool_use") is False:
            continue
        out[key] = m
    return out


def choose_reviewers(catalog: list[dict[str, Any]]) -> list[tuple[str, str, dict[str, Any]]]:
    """-> [(label, model_key, meta)] with labels fixed by list position."""
    by = available_tool_models(catalog)
    result = [(reviewer_label(i), key, by[key])
              for i, key in enumerate(REVIEWER_PRIMARY_MODELS, 1) if key in by]
    missing = [k for k in REVIEWER_PRIMARY_MODELS if k not in by]
    if USE_RESERVE_REVIEWERS and missing:
        n = len(REVIEWER_PRIMARY_MODELS)
        for key in REVIEWER_RESERVE_MODELS:
            if key in by and len(result) < len(REVIEWER_PRIMARY_MODELS):
                n += 1
                result.append((reviewer_label(n), key, by[key]))
    elif missing:
        print(f"[REVIEWERS] {len(missing)} configured reviewer(s) unavailable and will be skipped.")
    if not result:
        raise RuntimeError("None of the configured independent reviewer models are available.")
    return result


def choose_final(catalog: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    by = available_tool_models(catalog)
    if not by:
        raise RuntimeError("No usable final synthesis model is available.")
    ranked = sorted(by.items(), key=lambda it: (
        numeric_model_size(it[1]), int(it[1].get("max_context_length") or 0),
        1 if it[0] == FINAL_PRIMARY_MODEL else 0), reverse=True)
    if numeric_model_size(ranked[0][1]) > 0:
        return ranked[0]
    for key in [FINAL_PRIMARY_MODEL] + FINAL_RESERVE_MODELS:
        if key in by:
            return key, by[key]
    return ranked[0]



# ==========================================================================
# Shared guarded agent loop
# ==========================================================================
def _msg_chars(m: dict[str, Any]) -> int:
    return len(str(m.get("content") or "")) + (len(jcompact(m["tool_calls"])) if m.get("tool_calls") else 0)


def _group(tail: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Keep assistant(tool_calls)+tool results atomic."""
    groups, i = [], 0
    while i < len(tail):
        g = [tail[i]]
        first = tail[i]
        i += 1
        if first.get("role") == "assistant" and first.get("tool_calls"):
            while i < len(tail) and tail[i].get("role") == "tool":
                g.append(tail[i])
                i += 1
        groups.append(g)
    return groups


class AgentLoop:
    def __init__(self, *, client: LMStudioClient, model_key: str, label: str, system: str,
                 first_user: str, tools: list[dict[str, Any]],
                 executor: Callable[[str, dict[str, Any]], dict[str, Any]],
                 max_iterations: int, soft_tool_budget: int, max_tool_calls: int, max_seconds: float,
                 validator: Callable[["AgentLoop", str], str], finalize_hint: str = "",
                 log_name: str = "", fallback: Optional[Callable[["AgentLoop", str], str]] = None):
        self.client, self.model_key, self.label = client, model_key, label
        self.tools, self.executor = tools, executor
        self.max_iterations, self.soft_tool_budget = max_iterations, soft_tool_budget
        self.max_tool_calls, self.max_seconds = max_tool_calls, max_seconds
        self.validator, self.finalize_hint = validator, finalize_hint
        self.candidate = ""
        self.seen_paths: dict[str, None] = {}
        self.log_name, self.fallback_fn = log_name, fallback
        self.base = [{"role": "system", "content": system}, {"role": "user", "content": first_user}]
        self.tail: list[dict[str, Any]] = []
        self.ctx = client.context_length or 32_768
        self.compact_chars = int(max(30_000, min(600_000, self.ctx * CHARS_PER_TOKEN * 0.55)))
        self.ui = LiveUI()
        self.iterations = self.tool_calls = 0
        self.nudges = self.bad_turns = self.compactions = 0
        self.sig_counts: dict[str, int] = {}
        self.sig_iter: dict[str, int] = {}
        self.read_paths: dict[str, None] = {}
        self.history: list[dict[str, Any]] = []
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.last_prompt_tokens = 0
        self.loop_detected = False
        self.soft_hint_sent = self.time_hint_sent = False
        self.force_reason = ""
        self.started = time.perf_counter()
        self.last_finish: Optional[str] = None

    # -- bookkeeping ---------------------------------------------------------
    @property
    def messages(self) -> list[dict[str, Any]]:
        return self.base + self.tail

    def elapsed(self) -> float:
        return time.perf_counter() - self.started

    def _add_usage(self, usage: dict[str, Any]) -> None:
        for k in self.usage:
            try:
                self.usage[k] += int(usage.get(k) or 0)
            except (TypeError, ValueError):
                pass
        try:
            self.last_prompt_tokens = int(usage.get("prompt_tokens") or 0)
        except (TypeError, ValueError):
            pass

    def _user(self, text: str) -> None:
        self.tail.append({"role": "user", "content": text})

    def _limit_reason(self) -> str:
        if self.iterations > self.max_iterations:
            return f"iteration limit ({self.max_iterations})"
        if self.elapsed() > self.max_seconds:
            return f"time limit ({self.max_seconds / 60:.0f} min)"
        if self.tool_calls >= self.max_tool_calls:
            return f"tool-call limit ({self.max_tool_calls})"
        return self.force_reason

    # -- context compaction -----------------------------------------------------
    def _compact_if_needed(self) -> None:
        total = sum(_msg_chars(m) for m in self.messages)
        pressed = self.last_prompt_tokens > 0.7 * self.ctx
        if total < self.compact_chars and not pressed:
            return
        groups = _group(self.tail)
        keep_n = 8
        head_groups, recent = groups[:-keep_n], groups[-keep_n:]
        shrunk: list[list[dict[str, Any]]] = []
        for g in head_groups:                       # pass 1: shrink old tool output, keep head+tail
            ng = []
            for m in g:
                if m.get("role") == "tool" and len(str(m.get("content", ""))) > 1500:
                    c = str(m["content"])
                    ng.append({**m, "content": c[:900] + " …[old tool output shrunk]… " + c[-500:]})
                else:
                    ng.append(m)
            shrunk.append(ng)
        groups = shrunk + recent
        target = int(self.compact_chars * 0.6)
        while len(groups) > 2 and sum(_msg_chars(m) for g in groups for m in g) + _msg_chars(self.base[1]) > target:
            groups.pop(0)                           # pass 2: drop oldest groups
        self.tail = [m for g in groups for m in g]
        self.compactions += 1
        self.sig_counts.clear()                     # allow legitimate re-reads after compaction
        self.sig_iter.clear()
        read = ", ".join(list(self.read_paths)[-60:]) or "none"
        self.tail.insert(0, {"role": "user", "content": (
            "[Context was compacted: old tool output was shrunk or dropped. Already inspected: "
            f"{read}. Re-read only what is essential; otherwise continue and finish the audit.]")})

    # -- model turn -----------------------------------------------------------------
    def _turn(self, tools_on: bool, max_tokens: Optional[int] = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model_key, "messages": self.messages,
                                   "temperature": ANALYZER_TEMPERATURE, "tools": self.tools,
                                   "tool_choice": "auto" if tools_on else "none"}
        mt = max_tokens or MAX_COMPLETION_TOKENS
        if mt:
            payload["max_tokens"] = mt
        if ANALYZER_REASONING_EFFORT:
            payload["reasoning_effort"] = ANALYZER_REASONING_EFFORT
        self.ui.set_counts(self.iterations, self.tool_calls)
        append_prompt_log(self.log_name, self.label, {"t": now_iso(), "iter": self.iterations,
                          "chars": sum(_msg_chars(m) for m in self.messages), "tools_on": tools_on})
        resp = self.client.stream_chat(payload, self.ui)
        self._add_usage(resp.get("usage") or {})
        self.last_finish = resp.get("finish_reason")
        return resp

    # -- tools ----------------------------------------------------------------------
    @staticmethod
    def _pack(result: Any) -> str:
        s = jcompact(result)
        if len(s) <= MAX_TOOL_RESULT_CHARS:
            return s
        return jcompact({"truncated": True, "original_chars": len(s),
                         "preview": s[:MAX_TOOL_RESULT_CHARS - 400],
                         "hint": "Result too large; narrow it (read_lines / key / smaller max_chars)."})

    def _run_calls(self, calls: list[dict[str, Any]]) -> None:
        """Answers EVERY call (a missing tool result corrupts the protocol)."""
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name", "")
            raw = fn.get("arguments", "{}")
            cid = call.get("id") or f"call_{self.tool_calls}"
            self.ui.set_phase(f"tool: {name}")
            try:
                args = json.loads(raw) if isinstance(raw, str) and raw.strip() else (raw or {})
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
                err = None
            except Exception as exc:
                args, err = {}, f"invalid tool arguments: {exc}"

            sig = name + "|" + json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
            if self.tool_calls >= self.max_tool_calls:
                result: Any = {"error": "tool budget exhausted; write the final report now"}
            elif err:
                result = {"error": err, "raw": str(raw)[:500]}
            else:
                self.tool_calls += 1
                self.sig_counts[sig] = self.sig_counts.get(sig, 0) + 1
                n = self.sig_counts[sig]
                if n >= MAX_IDENTICAL_TOOL_CALLS + 2:
                    self.loop_detected = True
                    self.force_reason = f"tool-call loop on {name}"
                    result = {"error": "loop_detected", "message": "Refused. Write the final report now."}
                elif n >= 2:
                    if n >= MAX_IDENTICAL_TOOL_CALLS:
                        self.loop_detected = True
                    result = {"error": "duplicate_call",
                              "message": (f"Identical call already made in iteration {self.sig_iter.get(sig)}; "
                                          "result omitted. Use that result or call something different, "
                                          "or write the final audit.")}
                else:
                    try:
                        result = self.executor(name, args)
                    except Exception as exc:
                        result = {"error": f"{type(exc).__name__}: {exc}"}
                    self.sig_iter[sig] = self.iterations
                    if isinstance(result, dict) and "error" not in result:
                        if name in READ_TOOLS:
                            p = str(result.get("path") or args.get("path", ""))
                            self.read_paths[p] = None
                            self.seen_paths[p] = None
                        elif name == "search_text":
                            for mt in result.get("matches") or []:
                                self.seen_paths[str(mt.get("path", ""))] = None
            self.history.append({"iteration": self.iterations, "tool": name, "arguments": args,
                                 "result_summary": clip(jcompact(result), 400)})
            self.tail.append({"role": "tool", "tool_call_id": cid, "content": self._pack(result)})
            self.ui.set_counts(tool_calls=self.tool_calls)

    # -- finish helpers --------------------------------------------------------------
    def _result(self, status: str, text: str, reason: str = "") -> dict[str, Any]:
        self.ui.stop({"ANALYZED": "completed"}.get(status, status.lower()))
        return {"status": status, "stop_reason": reason, "iterations": self.iterations,
                "tool_calls": self.tool_calls, "elapsed_seconds": round(self.elapsed(), 1),
                "usage_total": self.usage, "analysis": text, "tool_history": self.history,
                "loop_detected": self.loop_detected, "compactions": self.compactions,
                "nudges": self.nudges, "bad_turns": self.bad_turns,
                "files_read": list(self.read_paths), "seen_paths": list(self.seen_paths)}

    def _force_finalize(self, reason: str) -> dict[str, Any]:
        self.ui.set_phase("finalizing")
        self._compact_if_needed()
        self._user(f"STOP INVESTIGATING ({reason}). Tools are now disabled. Write your final answer NOW from "
                   f"the evidence already gathered. {self.finalize_hint}")
        text = ""
        try:
            resp = self._turn(tools_on=False, max_tokens=min(12_000, MAX_COMPLETION_TOKENS or 12_000))
            if not resp.get("runaway"):
                text = (resp["message"].get("content") or "").strip()
        except LMStudioError as exc:
            reason += f"; finalize request failed: {exc}"
        if text:
            text = self._combine(text)
        elif self.candidate:
            text = self.candidate
        if len(text) >= 400:
            return self._result("ANALYZED_FORCED", text, reason)
        fb = self.fallback_fn(self, reason) if self.fallback_fn else f"Analysis incomplete: {reason}"
        return self._result("ANALYZER_LIMIT", fb, reason)

    def _combine(self, text: str) -> str:
        """A short reply after a nudge is a PATCH to the earlier long answer, not a replacement of it."""
        if self.candidate and len(text) < 0.85 * len(self.candidate):
            return self.candidate + "\n\n" + text
        return text

    # -- main loop -------------------------------------------------------------------
    def run(self) -> dict[str, Any]:
        self.ui.start(self.label, "starting")
        try:
            return self._run()
        except BaseException:
            self.ui.stop("error")
            raise

    def _run(self) -> dict[str, Any]:
        while True:
            self.iterations += 1
            limit = self._limit_reason()
            if limit:
                return self._force_finalize(limit)
            self._compact_if_needed()
            resp = self._turn(tools_on=True)
            msg = resp["message"]
            calls = msg.get("tool_calls") or []
            text = (msg.get("content") or "").strip()

            if resp.get("runaway"):                 # discard partial garbage entirely
                self.bad_turns += 1
                if self.bad_turns >= MAX_BAD_TURNS:
                    return self._force_finalize(f"{self.bad_turns} runaway generations ({resp['runaway']})")
                self._user(f"Your previous turn was discarded ({resp['runaway']}). Think briefly, then "
                           "either make ONE useful tool call or write the final audit.")
                continue

            if calls:
                self.tail.append(msg)
                self._run_calls(calls)
                hints = []
                if self.tool_calls >= self.soft_tool_budget and not self.soft_hint_sent:
                    self.soft_hint_sent = True
                    hints.append(f"Budget note: {self.tool_calls} tool calls used. Finish at most a few "
                                 "essential checks, then write the final audit.")
                if self.elapsed() > 0.75 * self.max_seconds and not self.time_hint_sent:
                    self.time_hint_sent = True
                    hints.append("Time note: most of the time budget is used. Write the final audit soon.")
                if self.loop_detected and not self.force_reason:
                    hints.append("You are repeating identical tool calls. Do not repeat them; use "
                                 "the evidence already gathered and finish the audit.")
                if hints:                           # only AFTER all tool results of this batch
                    self._user(" ".join(hints))
                continue

            # no tool calls -> candidate final answer
            if not text:
                self.bad_turns += 1
                if self.bad_turns >= MAX_BAD_TURNS:
                    return self._force_finalize("repeated empty responses")
                why = ("your reasoning used the whole token budget" if self.last_finish == "length"
                       else "no text was produced")
                self._user(f"Your last reply had no visible answer ({why}). Reason much more briefly, then make a "
                           "tool call or write the final answer.")
                continue
            combined = self._combine(text)
            problem = self.validator(self, combined)
            self.tail.append(msg)
            if not problem:
                return self._result("ANALYZED", combined)
            self.candidate = combined
            if self.nudges < MAX_FINAL_NUDGES:
                self.nudges += 1
                self._user(f"Not accepted yet: {problem} Send ONLY the missing/corrected part (for example the "
                           "corrected json block) - do not repeat the whole answer.")
                continue
            # Nudges exhausted: accept what we have instead of looping forever.
            return self._result("ANALYZED_LOW_EVIDENCE", combined, f"accepted after {self.nudges} nudges: {problem}")




# ==========================================================================
# Stage 0: deterministic preparation (no LLM): static analysis + test run
# ==========================================================================
def prepare_projects(benchmarks: list[Path], resume: bool) -> dict[str, dict[str, Any]]:
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict[str, Any]] = {}
    print("\n===== STAGE 0: static analysis + tests (no LLM) =====")
    for b in benchmarks:
        fp = project_fingerprint(b)
        cache = STATIC_DIR / f"{safe_name(b.name)}.json"
        data: Optional[dict[str, Any]] = None
        if resume and cache.exists():
            try:
                d = json.loads(read_text(cache))
                if d.get("fingerprint") == fp and d.get("schema") == SCHEMA_VERSION:
                    data = d
            except Exception:
                data = None
        if data is None:
            st = analyze_project(b)
            if st["empty"]:
                unit: dict[str, Any] = {"tests_run": 0, "ok": False, "summary": "no source files",
                                        "skipped": 0, "failures": 0, "errors": 0}
            else:
                unit = run_project_tests(source_root(b))
            data = {"schema": SCHEMA_VERSION, "fingerprint": fp, "static": st, "unit": unit}
            atomic_write(cache, jd(data))
            tag = "computed"
        else:
            tag = "cached"
        t, u = data["static"]["totals"], data["unit"]
        print(f"  [{tag}] {b.name}: src {t['src_files']} files/{t['src_loc']} loc, tests {u.get('tests_run')} "
              f"({'ok' if u.get('ok') else 'NOT ok'}), cov {u.get('coverage_percent')}, "
              f"max cc {t['max_complexity']}, cycles {len(t['import_cycles'])}, 3rd-party {t['third_party_src']}")
        out[b.name] = data
    return out


def same_model(reviewer_key: str, bench_name: str, summary: dict[str, Any]) -> bool:
    def last(s: Any) -> str:
        return re.sub(r"[^a-z0-9.]+", "-", str(s).lower().replace("__", "/").split("/")[-1])
    cands = [bench_name, (summary.get("model") or {}).get("key")]
    return any(c and last(c) == last(reviewer_key) for c in cands)


# ==========================================================================
# Audits
# ==========================================================================
def report_dir(bdir: Path, reviewer_id: str) -> Path:
    return bdir / "_analys" / safe_name(reviewer_id)


def write_audit(bdir: Path, name: str, reviewer_id: str, result: dict[str, Any], summary: dict[str, Any],
                extra: dict[str, Any]) -> None:
    out = report_dir(bdir, reviewer_id)
    old = out / "analys.json"
    if old.exists():
        try:
            stale = json.loads(read_text(old)).get("schema") != SCHEMA_VERSION
        except Exception:
            stale = True
        if stale:       # keep old-format reports instead of overwriting them
            shutil.move(str(out), str(out.parent / f"_archive_{datetime.now():%Y%m%d_%H%M%S}_{out.name}"))
    out.mkdir(parents=True, exist_ok=True)
    payload = dict(result)
    payload.update(extra, schema=SCHEMA_VERSION, benchmark_name=name, reviewer_id=reviewer_id,
                   benchmark_summary=benchmark_summary(summary), generated_at=now_iso())
    atomic_write(out / "analys.json", jd(payload))
    atomic_write(out / "analys.md", (
        "# Independent Benchmark Audit\n\n"
        f"- Benchmark: `{name}`\n- Reviewer: `{reviewer_id}`\n- Status: `{result.get('status')}`\n"
        f"- Stop reason: `{result.get('stop_reason', '')}`\n- Iterations: `{result.get('iterations')}`\n"
        f"- Tool calls: `{result.get('tool_calls')}`\n- Elapsed: `{result.get('elapsed_seconds')}` s\n\n---\n\n"
        f"{result.get('analysis', '')}\n"))


RETRY_WEAK = False
WEAK_STATUSES = {"ANALYZED_LOW_EVIDENCE", "ANALYZED_FORCED", "ANALYZER_LIMIT", "ANALYZER_ERROR"}


def existing_status(bdir: Path, reviewer_id: str) -> Optional[str]:
    try:
        d = json.loads(read_text(report_dir(bdir, reviewer_id) / "analys.json"))
        if d.get("schema") != SCHEMA_VERSION or (RETRY_WEAK and d.get("status") in WEAK_STATUSES):
            return None
        return d.get("status")
    except Exception:
        return None


def audit_fallback(loop: "AgentLoop", reason: str) -> str:
    files = ", ".join(loop.read_paths) or "none"
    return (f"## Audit incomplete\nThe reviewer could not produce a report: **{reason}**.\n\n"
            f"- Iterations: {loop.iterations}, tool calls: {loop.tool_calls}\n- Files inspected: {files}\n\n"
            "No rubric JSON was produced; this audit carries no weight.")


def build_first_user(reviewer_id: str, name: str, task: str, agent_prompt: str, inspector: Inspector,
                     summary: dict[str, Any], reqs: list[dict[str, str]], prep: dict[str, Any]) -> str:
    lines, truncated = inspector.tree_lines("", 120)
    bs = benchmark_summary(summary)
    files = bs["project"].get("files") or []
    if isinstance(files, list) and len(files) > 60:
        bs["project"]["files"] = files[:60] + [f"... {len(files) - 60} more"]
    if bs["agent"].get("loop_history") is not None:
        bs["agent"]["loop_history"] = clip(jcompact(bs["agent"]["loop_history"]), 2500)
    digest = static_digest(prep["static"])
    dj = jcompact(digest)
    if len(dj) > 9000:
        digest.pop("import_graph", None)
        dj = jcompact(digest)
    unit = {k: v for k, v in prep["unit"].items() if k not in ("stdout_tail",)}
    unit["stderr_tail"] = clip(str(unit.get("stderr_tail", "")), 2500)
    req_text = "\n".join(f"{r['id']}: {r['text']}" for r in reqs)
    return (
        f"NEW INDEPENDENT AUDIT. Reviewer ID: {reviewer_id}. Benchmark: {name}.\n\n"
        f"== ORIGINAL TASK ==\n{task}\n\n"
        f"== ORIGINAL AGENT SYSTEM PROMPT (reference only) ==\n{clip(agent_prompt, 3000)}\n\n"
        f"== REQUIREMENT CHECKLIST (give a status for EVERY id) ==\n{req_text}\n\n"
        f"== RUN SUMMARY (report.json; claims are unverified) ==\n{jcompact(bs)}\n\n"
        f"== STATIC METRICS (computed by script with ast; facts; cite as static:<field>) ==\n{dj}\n\n"
        f"== TEST EXECUTION (computed by script in a disposable copy; cite as `unittest`) ==\n{jcompact(unit)}\n\n"
        f"== FILES IN THE RESULT DIRECTORY ({len(lines)}{'+' if truncated else ''}) ==\n" + "\n".join(lines) + "\n\n"
        f"== EVALUATION RUBRIC ==\n{rubric_block()}\n\n"
        "== HOW TO WORK ==\n"
        "Open the core modules with read_lines (so you can cite path:line), one or two test files and the README. Use "
        "file_metrics for per-function numbers. Use run_probe to TEST behaviour: create thousands of records and time "
        "them, feed a corrupted storage file, bad CSV rows, call the CLI. Logs (events/tools/messages .jsonl) can be huge: "
        "use read_lines/search_text on them only for agent-behaviour questions.\n\n"
        f"{format_block(reqs)}")


def make_audit_validator(bdir: Path, reqs: list[dict[str, str]], prep: dict[str, Any], inspector: Inspector,
                         verification_failed: bool) -> Callable[["AgentLoop", str], str]:
    def validate(loop: "AgentLoop", text: str) -> str:
        checker = EvidenceChecker(bdir, set(loop.seen_paths), inspector.probes_run, True, prep["static"])
        ev = evaluate_audit(text, reqs, checker, prep["static"], prep["unit"], verification_failed)
        problems = list(ev["problems"])
        if not ev["valid"] and not problems:
            problems.append("The json block is incomplete.")
        if len(loop.read_paths) < MIN_AUDIT_READS:
            problems.append(f"Only {len(loop.read_paths)} file(s) were opened; open at least {MIN_AUDIT_READS} "
                            "(core modules, a test file, README) before concluding.")
        if loop.last_finish == "length":
            problems.append("The answer was cut off by the token limit; send a shorter audit and the json block.")
        return " ".join(problems[:3])
    return validate


def verification_failed_of(summary: dict[str, Any]) -> bool:
    v = summary.get("verification") or {}
    return bool(v.get("enabled") and not v.get("passed"))


def audit_all_with_judge(client: LMStudioClient, judge_key: str, reviewer_id: str, benchmarks: list[Path],
                         task: str, agent_prompt: str, system_prompt: str, reqs: list[dict[str, str]],
                         prepared: dict[str, dict[str, Any]], resume: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    print(f"\n===== REVIEWER {reviewer_id} =====")
    pending: list[Path] = []
    for b in benchmarks:
        summary = summary_for(b)
        if prepared[b.name]["static"]["empty"]:
            print(f"  [SKIP] {b.name}: no source files (nothing to audit)")
        elif same_model(judge_key, b.name, summary):
            print(f"  [SKIP] {b.name}: reviewer would judge its own output")
        elif resume and existing_status(b, reviewer_id) in COMPLETED_STATUSES:
            print(f"  [SKIP] {b.name}: already {existing_status(b, reviewer_id)}")
        else:
            pending.append(b)
    if not pending:
        return results

    try:
        client.assert_empty()
        client.load_model(judge_key)
        print("  [LM] loaded + verified; every project gets a NEW CHAT")
        for index, bdir in enumerate(pending, 1):
            name = bdir.name
            print(f"[{index}/{len(pending)}] {name} -> {reviewer_id}")
            summary, prep = summary_for(bdir), prepared[name]
            inspector = Inspector(bdir, prep["static"], prep["unit"])
            try:
                loop = AgentLoop(
                    client=client, model_key=judge_key, label=reviewer_id, system=system_prompt,
                    first_user=build_first_user(reviewer_id, name, task, agent_prompt, inspector, summary, reqs, prep),
                    tools=AUDIT_TOOLS, executor=make_audit_executor(inspector),
                    max_iterations=MAX_AUDITOR_ITERATIONS, soft_tool_budget=SOFT_TOOL_BUDGET,
                    max_tool_calls=MAX_AUDITOR_TOOL_CALLS, max_seconds=MAX_AUDIT_SECONDS,
                    validator=make_audit_validator(bdir, reqs, prep, inspector, verification_failed_of(summary)),
                    finalize_hint=("Follow the FINAL ANSWER FORMAT from the first message: a SHORT audit and then the "
                                   "json block with ALL requirement ids and ALL dimensions. Unverified items: "
                                   "status UNVERIFIED / score <= 2."),
                    log_name=name, fallback=audit_fallback)
                audit = loop.run()
            except LMStudioError as exc:
                audit = {"status": "ANALYZER_ERROR", "analysis": f"LM Studio error: {exc}", "seen_paths": []}
            except Exception as exc:
                audit = {"status": "ANALYZER_ERROR", "seen_paths": [],
                         "analysis": f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"}
            audit.update(reviewer_id=reviewer_id, benchmark_name=name)
            write_audit(bdir, name, reviewer_id, audit, summary, {"probes_run": inspector.probes_run})
            results.append(audit)
            print(f"  [DONE] {audit.get('status')} | iter {audit.get('iterations')} | tools {audit.get('tool_calls')} "
                  f"| probes {inspector.probes_run} | {audit.get('elapsed_seconds')}s")
    finally:
        print("  [LM] unload reviewer + VERIFY")
        client.unload_all_verified()
        client.assert_empty()
    return results


# ==========================================================================
# Aggregation (pure Python; the LLM never computes scores)
# ==========================================================================
def weighted_median(pairs: list[tuple[float, float]]) -> float:
    pairs = sorted((v, w) for v, w in pairs if w > 0)
    if not pairs:
        return 0.0
    total, acc = sum(w for _, w in pairs), 0.0
    for i, (v, w) in enumerate(pairs):
        acc += w
        if abs(acc - total / 2) < 1e-9 and i + 1 < len(pairs):
            return (v + pairs[i + 1][0]) / 2
        if acc > total / 2:
            return v
    return pairs[-1][0]


def load_audits(bdir: Path, reqs: list[dict[str, str]], prep: dict[str, Any], summary: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    root = bdir / "_analys"
    if not root.is_dir():
        return out
    for d in sorted(root.glob("ANALYST_*")):
        try:
            data = json.loads(read_text(d / "analys.json"))
        except Exception:
            continue
        if data.get("schema") != SCHEMA_VERSION:
            continue
        checker = EvidenceChecker(bdir, set(data.get("seen_paths") or []), int(data.get("probes_run") or 0), True,
                                  prep["static"])
        ev = evaluate_audit(str(data.get("analysis", "")), reqs, checker, prep["static"], prep["unit"],
                            verification_failed_of(summary))
        thin = int(data.get("tool_calls") or 0) < 3 or len(data.get("files_read") or []) < MIN_AUDIT_READS
        weight = 0.0 if (not ev["valid"] or thin) else round(0.5 + 0.5 * ev["evidence_valid_ratio"], 3)
        out.append({"reviewer": d.name, "weight": weight, "ev": ev, "status": data.get("status"),
                    "iterations": data.get("iterations"), "tool_calls": data.get("tool_calls"),
                    "elapsed_seconds": data.get("elapsed_seconds"), "thin": thin})
    return out


def aggregate_benchmark(bdir: Path, reqs: list[dict[str, str]], prep: dict[str, Any]) -> dict[str, Any]:
    summary = summary_for(bdir)
    st, unit = prep["static"], prep["unit"]
    audits = load_audits(bdir, reqs, prep, summary)
    used = [a for a in audits if a["weight"] > 0]
    bench = summary.get("benchmark") or {}
    agent, tokens = summary.get("agent") or {}, summary.get("tokens") or {}
    info: dict[str, Any] = {
        "benchmark": bdir.name, "model_key": (summary.get("model") or {}).get("key"),
        "static": st["totals"], "syntax_errors": st["syntax_errors"], "unit": unit,
        "process": {"status": bench.get("status"), "stop_reason": bench.get("stop_reason"),
                    "duration_seconds": bench.get("duration_seconds"), "iterations": agent.get("iterations"),
                    "tool_calls": agent.get("tool_calls"), "failed_tool_calls": agent.get("failed_tool_calls"),
                    "total_tokens": tokens.get("total_tokens"), "verification": summary.get("verification") or {}},
        "reviews": [], "rankable": False, "reason": "", "score": None, "confidence": "none", "n_reviewers": len(used),
        "spread": None, "dimensions": {}, "dimension_spread": {}, "completeness_pct": None, "requirements": {},
        "disagreements": [], "flags": []}
    for a in audits:
        e = a["ev"]
        info["reviews"].append({"reviewer": a["reviewer"], "weight": a["weight"], "valid": e["valid"],
                                "overall": e["overall"], "claimed_overall": e["claimed_overall"],
                                "termination": e["termination"], "confidence": e["confidence"],
                                "evidence_valid_ratio": e["evidence_valid_ratio"], "critical": e["critical"],
                                "strengths": e["strengths"], "weaknesses": e["weaknesses"], "caps": e["caps"],
                                "problems": e["problems"][:2], "thin": a["thin"], "status": a["status"],
                                "tool_calls": a["tool_calls"], "elapsed_seconds": a["elapsed_seconds"],
                                "dim_scores": {k: v["score"] for k, v in e["dimensions"].items()}})
    flags = info["flags"]
    if st["empty"]:
        le = bdir / "load_error.txt"
        info["reason"] = "no source files produced" + (f" (load_error: {clip(read_text(le).strip(), 160)})" if le.exists() else "")
        return info
    if not used:
        info["reason"] = "no valid reviewer audit (invalid rubric JSON, too little evidence or no audits yet)"
        return info
    pairs = lambda f: [(f(a), a["weight"]) for a in used]
    comp = weighted_median(pairs(lambda a: a["ev"]["completeness_ratio"]))
    dims = {k: round(weighted_median(pairs(lambda a, k=k: a["ev"]["dimensions"][k]["score"])), 2) for k in DIM_KEYS}
    info["dimensions"] = {"completeness": round(5 * comp, 2), **dims}
    info["completeness_pct"] = round(100 * comp, 1)
    for k in DIM_KEYS:
        vals = [a["ev"]["dimensions"][k]["score"] for a in used]
        spread = max(vals) - min(vals)
        info["dimension_spread"][k] = spread
        if spread >= 2:
            info["disagreements"].append({"dimension": k, "scores": {a["reviewer"]: a["ev"]["dimensions"][k]["score"]
                                                                       for a in used}})
    overall = 100 * (COMPLETENESS_WEIGHT * comp + sum(DIMENSIONS[k]["weight"] * dims[k] / 5 for k in DIM_KEYS))
    info["score"] = round(overall, 1)
    ov = [a["ev"]["overall"] for a in used]
    info["spread"] = round(max(ov) - min(ov), 1)
    n = len(used)
    info["confidence"] = "high" if n >= 3 and info["spread"] <= 15 else "medium" if n >= 2 and info["spread"] <= 30 else "low"
    for r in reqs:
        votes: dict[str, float] = {}
        for a in used:
            s = a["ev"]["requirements"].get(r["id"], {}).get("status", "MISSING")
            votes[s] = votes.get(s, 0) + a["weight"]
        info["requirements"][r["id"]] = max(votes.items(), key=lambda kv: (kv[1], kv[0] == "FAIL"))[0] if votes else "?"
    t = st["totals"]
    if verification_failed_of(summary):
        flags.append("verification_failed")
    if not unit.get("tests_run"):
        flags.append("no_tests_ran")
    elif not unit.get("ok"):
        flags.append("tests_failing")
    if t["third_party_src"]:
        flags.append("third_party_imports")
    if t["import_cycles"]:
        flags.append("import_cycles")
    if st["syntax_errors"]:
        flags.append("syntax_errors")
    if (bench.get("status") or "SUCCESS") != "SUCCESS":
        flags.append(f"agent_{str(bench.get('status')).lower()}")
    terms = [a["ev"]["termination"] for a in used]
    if any(x in ("infrastructure_failure", "user_interrupted", "mixed_model_and_infrastructure") for x in terms):
        flags.append("infrastructure_suspected")
    if info["confidence"] == "low":
        flags.append("low_confidence")
    info["rankable"] = True
    return info


def aggregate_all(benchmarks: list[Path], reqs: list[dict[str, str]],
                  prepared: dict[str, dict[str, Any]]) -> dict[str, Any]:
    items = [aggregate_benchmark(b, reqs, prepared[b.name]) for b in benchmarks]
    ranked = sorted((i for i in items if i["rankable"]), key=lambda i: (-i["score"], -(i["completeness_pct"] or 0)))
    for n, i in enumerate(ranked, 1):
        i["rank"] = n
    unranked = [i for i in items if not i["rankable"]]
    rel: dict[str, dict[str, Any]] = {}
    for i in items:
        for r in i["reviews"]:
            s = rel.setdefault(r["reviewer"], {"audits": 0, "valid": 0, "zero_weight": 0, "ev": [], "tools": [],
                                              "secs": [], "dev": [], "bias": []})
            s["audits"] += 1
            s["valid"] += 1 if r["valid"] else 0
            s["zero_weight"] += 1 if r["weight"] == 0 else 0
            if r["valid"]:
                s["ev"].append(r["evidence_valid_ratio"])
            s["tools"].append(r["tool_calls"] or 0)
            s["secs"].append(r["elapsed_seconds"] or 0)
            if r["valid"] and r["overall"] is not None and i["score"] is not None:
                s["dev"].append(r["overall"] - i["score"])
                s["bias"].append((r["claimed_overall"] or 0) - i["score"])
    mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
    reliability = [{"reviewer": k, "audits": v["audits"], "valid_rubric_pct": round(100 * v["valid"] / v["audits"]),
                    "zero_weight_audits": v["zero_weight"], "avg_evidence_valid": mean(v["ev"]),
                    "avg_tool_calls": mean(v["tools"]), "avg_seconds": mean(v["secs"]),
                    "mean_abs_deviation": mean([abs(x) for x in v["dev"]]), "claimed_bias": mean(v["bias"])}
                   for k, v in sorted(rel.items())]
    return {"ranked": ranked, "unranked": unranked, "reliability": reliability, "all": items}


# ==========================================================================
# Report rendering (deterministic, Russian)
# ==========================================================================
def short(name: str) -> str:
    return name.replace("__", "/")


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    esc = lambda x: ("" if x is None else str(x)).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(esc(h) for h in headers) + " |", "|" + "|".join("---" for _ in headers) + "|",
                      *["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]])


def render_report(agg: dict[str, Any], reqs: list[dict[str, str]], commentary: str,
                  metadata: dict[str, Any]) -> str:
    ranked, unranked = agg["ranked"], agg["unranked"]
    L: list[str] = ["# Анализ бенчмарка LLM-агентов (v9: рубрика + статический анализ + скрипт-агрегация)", "",
                    f"Сгенерировано: {now_iso()}", ""]
    L += ["## 1. Итоговый рейтинг", "",
          "Баллы посчитаны скриптом (взвешенная медиана по аналитикам), не нейросетью. "
          "Модель-судья не может изменить числа.", ""]
    rows = []
    for i in ranked:
        u, t = i["unit"], i["static"]
        rows.append([i["rank"], short(i["benchmark"]), i["score"], f"{i['confidence']} ({i['n_reviewers']} анал., разброс {i['spread']})",
                     f"{i['completeness_pct']}%", f"{u.get('tests_run')} / {'ok' if u.get('ok') else 'FAIL'}",
                     u.get("coverage_percent"), f"{t['src_loc']}/{t['test_loc']}", i["process"]["status"],
                     ", ".join(i["flags"]) or "-"])
    L += [md_table(["#", "Модель", "Балл", "Уверенность", "Полнота треб.", "Тесты", "Покрытие %", "LOC src/test",
                    "Агент", "Флаги"], rows), ""]
    L += ["## 2. Оценки по измерениям (медиана аналитиков, шкала 0–5)", ""]
    labels = {"completeness": "Полнота"} | {k: v["label"] for k, v in DIMENSIONS.items()}
    L += [md_table(["Модель"] + list(labels.values()),
                   [[short(i["benchmark"])] + [i["dimensions"].get(k) for k in labels] for i in ranked]), ""]
    L += ["Веса: " + ", ".join(f"{labels[k]} {int(w * 100)}%" for k, w in WEIGHTS.items()) + ".", ""]
    if unranked:
        L += ["## 3. Нерейтингуемые результаты", ""]
        L += [f"- `{short(i['benchmark'])}`: {i['reason']}" for i in unranked] + [""]
    L += ["## 4. Матрица требований (консенсус аналитиков)", "",
          "✅ PASS · ◐ PARTIAL · ❌ FAIL · ❓ UNVERIFIED/нет данных", ""]
    sym = {"PASS": "✅", "PARTIAL": "◐", "FAIL": "❌"}
    L += [md_table(["ID", "Требование"] + [short(i["benchmark"]).split("/")[-1][:18] for i in ranked],
                   [[r["id"], clip(r["text"], 70)] + [sym.get(i["requirements"].get(r["id"]), "❓") for i in ranked]
                    for r in reqs]), ""]
    L += ["## 5. Структура кода (статический анализ, факты)", ""]
    srows = []
    for i in ranked + unranked:
        t = i["static"]
        srows.append([short(i["benchmark"]), f"{t['src_files']}/{t['test_files']}", t["src_loc"], t["functions"],
                      f"{t['avg_complexity']}/{t['max_complexity']}", t["funcs_len_gt50"], t["docstring_pct_public"],
                      t["annotation_pct_public"], len(t["import_cycles"]), ",".join(t["third_party_src"]) or "-",
                      t["bare_except"], t["test_methods"], t["avg_asserts_per_test"], t["tests_without_assert"]])
    L += [md_table(["Модель", "Файлов src/test", "LOC", "Функций", "CC ср./макс", "Функций >50 строк", "Docstring %",
                    "Type hints %", "Циклы имп.", "Сторонние имп.", "bare except", "Тестов", "assert/тест",
                    "Тестов без assert"], srows), ""]
    L += ["## 6. Процесс агента (из report.json)", ""]
    prow = [[short(i["benchmark"]), i["process"]["status"], i["process"]["stop_reason"], i["process"]["duration_seconds"],
             i["process"]["iterations"], i["process"]["tool_calls"], i["process"]["failed_tool_calls"],
             i["process"]["total_tokens"]] for i in ranked + unranked]
    L += [md_table(["Модель", "Статус", "Причина остановки", "Секунд", "Итераций", "Вызовов", "Ошибок вызовов",
                    "Токенов"], prow), ""]
    L += ["## 7. Расхождения аналитиков (измерения с разбросом ≥ 2 баллов)", ""]
    any_dis = False
    for i in ranked:
        if i["disagreements"] or (i["spread"] or 0) >= 25:
            any_dis = True
            L.append(f"- **{short(i['benchmark'])}** (разброс общего балла {i['spread']}): " + "; ".join(
                f"{d['dimension']}: " + ", ".join(f"{r}={s:g}" for r, s in d["scores"].items())
                for d in i["disagreements"]))
    L += ([""] if any_dis else ["Существенных расхождений нет.", ""])
    L += ["## 8. Надёжность аналитиков", "",
          "Вес аудита = 0, если JSON рубрики невалиден, мало инструментальных проверок или нет файлов, которые судья "
          "реально открыл. Вес 0.5–1.0 растёт с долей подтверждённых ссылок на доказательства. "
          "«Заявленное смещение» = (баллы, которые судья сам выставил до проверки) − консенсус: "
          "большое положительное значение = раздача завышенных оценок.", ""]
    L += [md_table(["Аналитик", "Аудитов", "Валидный JSON %", "Аудитов с весом 0", "Подтв. ссылок", "Ср. вызовов",
                    "Ср. сек", "Ср. откл. (после проверки)", "Заявленное смещение"],
                   [[r["reviewer"], r["audits"], r["valid_rubric_pct"], r["zero_weight_audits"], r["avg_evidence_valid"],
                     r["avg_tool_calls"], r["avg_seconds"], r["mean_abs_deviation"], r["claimed_bias"]]
                    for r in agg["reliability"]]), ""]
    L += ["## 9. Комментарий финального аналитика (интерпретация, числа не изменяет)", "",
          commentary.strip() or "_Комментарий не создан (этап пропущен или завершился с ошибкой)._", ""]
    L += ["## 10. Методика", "",
          "1. Скрипт строит статические метрики (ast), запускает unittest (и coverage, если установлен) в одноразовой копии.",
          "2. Каждый аналитик проверяет проект по рубрике и возвращает JSON: статусы требований и оценки 0–5 с ссылками "
          "`path:line`, `static:`, `unittest`, `probe:N`.",
          "3. Скрипт проверяет ссылки: файл существует, строка есть, судья файл открывал. Непроверенное режется "
          "(оценка ≤ 2, PASS → 0.4 кредита).",
          "4. Жёсткие потолки из фактов: 0 тестов → testing ≤ 1; падающие тесты → ≤ 2; сторонние импорты → "
          "constraint ≤ 1; синтаксические ошибки; провал независимой верификации → полнота ≤ 70%.",
          "5. Итог — взвешенная медиана аналитиков по каждому измерению; полнота считается из матрицы требований.",
          "6. Аналитик не оценивает собственную модель.", "",
          "```json", jd({k: v for k, v in metadata.items()}), "```", ""]
    return "\n".join(L)


def write_outputs(agg: dict[str, Any], reqs: list[dict[str, str]], commentary: str, metadata: dict[str, Any]) -> None:
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write(ANALYSIS_DIR / "FULL_ANALYSIS_REPORT.md", render_report(agg, reqs, commentary, metadata))

    def slim(i: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in i.items() if k != "unit"} | {
            "unit": {k: v for k, v in i["unit"].items() if k not in ("stdout_tail", "stderr_tail")}}
    atomic_write(ANALYSIS_DIR / "RANKING.json", jd({"metadata": metadata, "requirements": reqs, "weights": WEIGHTS,
                                                    "ranked": [slim(i) for i in agg["ranked"]],
                                                    "unranked": [slim(i) for i in agg["unranked"]],
                                                    "reviewer_reliability": agg["reliability"]}))
    with (ANALYSIS_DIR / "RANKING.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "benchmark", "score", "confidence", "completeness_pct", "tests_run", "tests_ok",
                    "coverage", *DIM_KEYS, "flags"])
        for i in agg["ranked"]:
            w.writerow([i["rank"], i["benchmark"], i["score"], i["confidence"], i["completeness_pct"],
                        i["unit"].get("tests_run"), i["unit"].get("ok"), i["unit"].get("coverage_percent"),
                        *[i["dimensions"].get(k) for k in DIM_KEYS], ";".join(i["flags"])])


# ==========================================================================
# Final commentary (LLM interprets; numbers come from the script)
# ==========================================================================
def commentary_payload(agg: dict[str, Any]) -> str:
    out = []
    for i in agg["ranked"] + agg["unranked"]:
        t, u = i["static"], i["unit"]
        out.append({
            "benchmark": i["benchmark"], "rank": i.get("rank"), "score": i["score"], "confidence": i["confidence"],
            "rankable": i["rankable"], "not_rankable_reason": i["reason"], "flags": i["flags"],
            "dimensions_0_5": i["dimensions"], "completeness_pct": i["completeness_pct"],
            "tests": {"run": u.get("tests_run"), "ok": u.get("ok"), "coverage": u.get("coverage_percent")},
            "static": {k: t[k] for k in ("src_files", "src_loc", "functions", "avg_complexity", "max_complexity",
                                         "funcs_len_gt50", "docstring_pct_public", "annotation_pct_public",
                                         "import_cycles", "third_party_src", "bare_except", "test_methods",
                                         "avg_asserts_per_test")},
            "process": {k: i["process"][k] for k in ("status", "stop_reason", "duration_seconds", "iterations",
                                                     "tool_calls", "failed_tool_calls")},
            "disagreements": i["disagreements"],
            "reviews": [{"reviewer": r["reviewer"], "weight": r["weight"], "overall": r["overall"],
                         "termination": r["termination"], "critical": r["critical"][:3],
                         "strengths": r["strengths"][:3], "weaknesses": r["weaknesses"][:3]} for r in i["reviews"]],
        })
    return jcompact(out)


def make_final_executor(benchmarks: list[Path]) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    def run(name: str, a: dict[str, Any]) -> dict[str, Any]:
        allowed = {safe_rel(RESULTS_DIR, p): p for p in
                   (q for b in benchmarks for q in (b / "_analys").glob("ANALYST_*/analys.md"))}
        if name == "list_reports":
            return {"reports": sorted(allowed)}
        if name == "read_report":
            rel = norm_path(str(a.get("path", "")))
            if rel not in allowed:
                return {"error": "unknown report path", "valid_examples": sorted(allowed)[:5]}
            data = read_text(allowed[rel])
            off = max(0, _int(a, "offset", 0))
            lim = min(_int(a, "max_chars", MAX_READ_CHARS_PER_CALL), MAX_READ_CHARS_PER_CALL)
            res = {"path": rel, "total_chars": len(data), "content": data[off:off + lim],
                   "has_more": off + lim < len(data)}
            if off + lim < len(data):
                res["next_offset"] = off + lim
            return res
        return {"error": f"unknown tool {name!r}"}
    return run


FINAL_TOOLS = [
    _tool("list_reports", "List raw audit report paths (optional deep dive).", {}, []),
    _tool("read_report", "Read a raw audit report (analys.md) in chunks, only when you must resolve a disagreement.",
          {"path": _S, "offset": _I, "max_chars": _I}, ["path"]),
]


def run_commentary(client: LMStudioClient, model_key: str, benchmarks: list[Path], agg: dict[str, Any],
                   task: str) -> dict[str, Any]:
    def validate(loop: "AgentLoop", text: str) -> str:
        if len(text) < MIN_FINAL_CHARS:
            return f"The commentary is too short ({len(text)} chars); cover all six sections."
        if loop.last_finish == "length":
            return "The commentary was cut off; continue with the remaining sections only."
        return ""

    def fb(loop: "AgentLoop", reason: str) -> str:
        return f"_Финальный аналитик не смог завершить комментарий: {reason}. Все таблицы выше посчитаны скриптом._"

    loop = AgentLoop(
        client=client, model_key=model_key, label="FINAL_ANALYST", system=AGG_SYSTEM,
        first_user=(f"ORIGINAL BENCHMARK TASK:\n{clip(task, 3000)}\n\nDATA SET (JSON, scores already computed by the "
                    f"script):\n{commentary_payload(agg)}\n\nWrite the commentary now."),
        tools=FINAL_TOOLS, executor=make_final_executor(benchmarks),
        max_iterations=MAX_FINAL_ITERATIONS, soft_tool_budget=MAX_FINAL_TOOL_CALLS - 20,
        max_tool_calls=MAX_FINAL_TOOL_CALLS, max_seconds=MAX_FINAL_SECONDS, validator=validate,
        finalize_hint="Write the commentary now in Russian from the data you have (the six sections).",
        log_name="_FINAL_COMMENTARY", fallback=fb)
    return loop.run()


# ==========================================================================
# main
# ==========================================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-judge LM benchmark analyzer v9")
    ap.add_argument("--no-resume", action="store_true", help="re-run static analysis and audits even if finished")
    ap.add_argument("--skip-final", action="store_true", help="no LLM commentary")
    ap.add_argument("--final-only", action="store_true", help="skip reviewers, only commentary")
    ap.add_argument("--retry-weak", action="store_true",
                    help="redo audits that ended forced / low-evidence / with an error")
    ap.add_argument("--rescore", action="store_true",
                    help="no models at all: recompute scores from stored audits and rebuild the report")
    args = ap.parse_args()
    resume = RESUME and not args.no_resume
    global RETRY_WEAK
    RETRY_WEAK = args.retry_weak

    print("=== MULTI-JUDGE LM BENCHMARK ANALYZER v9 (rubric + static analysis + scripted scoring) ===")
    benchmarks = discover_benchmark_dirs()
    if not benchmarks:
        print("[ERROR] No benchmark result directories found.")
        return 2
    task = read_text(TASK_FILE) if TASK_FILE.exists() else "[task.txt missing]"
    agent_prompt = read_text(SYSTEM_PROMPT_FILE) if SYSTEM_PROMPT_FILE.exists() else "[system_prompt.txt missing]"
    reqs = load_requirements(task)
    print(f"[REQUIREMENTS] {len(reqs)} (edit config/requirements.txt, one per line, to control this list):")
    for r in reqs:
        print(f"  {r['id']}: {clip(r['text'], 110)}")
    for old in (ANALYZER_SYSTEM_PROMPT_FILE, ANALYZER_TASK_FILE):
        if old.exists():
            print(f"[NOTE] {old.name} is ignored in v9 (output format is fixed). Put extra guidance into "
                  f"{ANALYZER_EXTRA_FILE.name}.")
    extra = load_optional(ANALYZER_EXTRA_FILE)
    system_prompt = BASE_SYSTEM + (f"\n\nOPERATOR GUIDANCE:\n{extra}" if extra else "") + PROTOCOL_RULES

    prepared = prepare_projects(benchmarks, resume)
    client = LMStudioClient(token=os.environ.get("LM_API_TOKEN", ""))
    reviewers: list[tuple[str, str, dict[str, Any]]] = []
    final_model = ""
    interrupted = False
    commentary_file = ANALYSIS_DIR / "commentary.md"
    commentary = read_text(commentary_file) if commentary_file.exists() else ""

    if not args.rescore:
        try:
            initial = client.loaded_instances()
            if initial:
                print("[ERROR] LM Studio already has loaded models; analyzer will NOT touch them:")
                print(jd(initial))
                return 3
            catalog = client.model_catalog()
            reviewers = choose_reviewers(catalog)
            final_model, _ = choose_final(catalog)
        except Exception as exc:
            print(f"[ERROR] Setup failed: {exc}")
            return 2
        print("[REVIEWERS] " + ", ".join(label for label, _, _ in reviewers))

    metadata_base = {"schema": SCHEMA_VERSION, "benchmarks": [b.name for b in benchmarks],
                     "reviewer_ids": [label for label, _, _ in reviewers] or "see audits",
                     "requirements": len(reqs)}

    try:
        if not args.rescore and not args.final_only:
            for label, judge_key, _meta in reviewers:
                try:
                    audit_all_with_judge(client, judge_key, label, benchmarks, task, agent_prompt, system_prompt,
                                         reqs, prepared, resume)
                except LMStudioError as exc:
                    print(f"[ERROR] reviewer {label} failed: {exc}")
                    client.unload_all_verified()

        ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        agg = aggregate_all(benchmarks, reqs, prepared)
        write_outputs(agg, reqs, commentary, dict(metadata_base, generated_at=now_iso(), interrupted=False))
        print(f"\n[REPORT] deterministic report written: {ANALYSIS_DIR / 'FULL_ANALYSIS_REPORT.md'}")

        if not args.rescore and not args.skip_final and agg["ranked"]:
            print("\n===== FINAL COMMENTARY =====")
            client.unload_all_verified()
            client.assert_empty()
            client.load_model(final_model)
            try:
                res = run_commentary(client, final_model, benchmarks, agg, task)
                commentary = str(res.get("analysis", ""))
                atomic_write(commentary_file, commentary)
            finally:
                client.unload_all_verified()
                client.assert_empty()
            write_outputs(agg, reqs, commentary, dict(metadata_base, generated_at=now_iso(), interrupted=False))
    except KeyboardInterrupt:
        interrupted = True
        print("\n[INTERRUPTED] unloading models; finished audits are kept and will be resumed.")
        try:
            client.unload_all_verified()
        except Exception as exc:
            print(f"[WARN] unload after interrupt failed: {exc}")
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        try:
            client.unload_all_verified()
        except Exception as unload_exc:
            print(f"[WARN] unload failed: {unload_exc}")
        return 1

    print("\n=== INTERRUPTED ===" if interrupted else "\n=== COMPLETE ===")
    print(f"Report:  {ANALYSIS_DIR / 'FULL_ANALYSIS_REPORT.md'}")
    print(f"Data:    {ANALYSIS_DIR / 'RANKING.json'} / RANKING.csv")
    print("Rebuild without any model:  python analyzer.py --rescore")
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())

# CHANGELOG v8 -> v9
# 1. Scores are computed by this script, never by an LLM: rubric JSON per reviewer -> evidence validation ->
#    weighted medians. The final LLM only writes commentary (no table, no arithmetic, no 'Score:' line).
# 2. New objective stage 0: ast-based architecture/quality metrics (modules, import graph + cycles, complexity,
#    function length, docstrings, type hints, error handling, duplicates, test structure), unittest + coverage.
# 3. Judges evaluate engineering: architecture, extensibility/scalability (with run_probe measurements), code quality,
#    robustness, tests, docs, constraints; completeness comes from a per-requirement matrix.
# 4. Anti-sycophancy: unverifiable claims are capped, 5/5 needs proof, reviewers who open nothing get weight 0.
# 5. A reviewer never judges its own model; stable ANALYST labels; v8 audits are archived, not overwritten.
# 6. Fixed my v8 bug: the final report was forced to contain 'Score: NN/100', and a nudge reply replaced the report.