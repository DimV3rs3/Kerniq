"""Benchmark the models of the selected provider, one after another, on the same task.

Each slot has its own system prompt and task (up to three). After the runs,
anonymous analyzers share one prompt and see the outputs labeled A/B/C.
One main analyzer writes the report with its own prompt and task.
Everything lands in <workspace>/benchmarks. Paths outside the workspace are refused.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from Kerniq.core.agent import Agent
from Kerniq.interfaces.models import Message, MessageRole, ModelRequest
from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.plugins.manifest import PluginManifest

logger = logging.getLogger(__name__)

_LABELS = ("A", "B", "C")
_MAX_SLOTS = 3
_BENCH_LOCK = threading.Lock()
_FAIL_OUTCOMES = {
    "provider_error",
    "verification_failed",
    "tool_loop",
    "content_loop",
    "empty_response",
    "no_plan",
    "max_iterations",
}


def _text(values: Dict[str, Any], key: str) -> str:
    raw = values.get(key)
    if raw is None:
        return ""
    return str(raw).strip()


def _int(values: Dict[str, Any], key: str, default: int, low: int, high: int) -> int:
    try:
        value = int(values.get(key) if values.get(key) is not None else default)
    except (TypeError, ValueError):
        value = default
    return max(low, min(high, value))


def workspace_root(context: Any) -> Path:
    raw = None
    if isinstance(context, dict):
        raw = context.get("workspace")
    else:
        raw = getattr(context, "workspace", None)
    if not raw:
        raw = "./workspace"
    return Path(str(raw)).expanduser().resolve()


def results_dir(workspace: Path, configured: str) -> Path:
    """Empty means <workspace>/benchmarks. Anything outside the workspace is refused."""
    base = (workspace / "benchmarks").resolve()
    text = (configured or "").strip()
    if not text:
        target = base
    else:
        candidate = Path(text).expanduser()
        if not candidate.is_absolute():
            candidate = workspace / candidate
        target = candidate.resolve()
    try:
        target.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Results folder must stay inside the Kerniq workspace ({workspace})."
        ) from exc
    target.mkdir(parents=True, exist_ok=True)
    return target


def slots_from(values: Dict[str, Any]) -> List[Dict[str, str]]:
    """Up to three independent (system prompt, task) pairs.

    ``slot_count`` limits how many of those pairs are used. When it is absent,
    every pair that has a task or a system prompt is kept.
    """
    raw_count = values.get("slot_count")
    limit = _MAX_SLOTS
    if raw_count is not None and str(raw_count).strip() != "":
        limit = _int(values, "slot_count", 1, 1, _MAX_SLOTS)
    found: List[Dict[str, str]] = []
    fallback_task = _text(values, "task")
    for index in range(1, limit + 1):
        task = _text(values, f"task_{index}")
        system = _text(values, f"system_{index}")
        if index == 1 and not task:
            task = fallback_task
        if not task and not system:
            continue
        found.append({"system": system, "task": task or fallback_task})
    if not found and fallback_task and limit >= 1:
        found.append({"system": "", "task": fallback_task})
    return found[:limit]


def _model_ids(listed: List[Dict[str, Any]], selected: str) -> List[str]:
    return [row["id"] for row in prepare_models(listed)]


def _is_chat_model(item: Dict[str, Any], model_id: str) -> bool:
    kind = str(item.get("type") or "").lower()
    if kind in {"embedding", "embeddings", "embed", "rerank"}:
        return False
    blob = f"{model_id} {item.get('name') or ''}".lower()
    return "embed" not in blob and "rerank" not in blob


def _weight_of(item: Dict[str, Any]) -> int:
    try:
        direct = int(item.get("weight_bytes") or 0)
    except (TypeError, ValueError):
        direct = 0
    if direct > 0:
        return direct
    try:
        from Kerniq.models.providers.lm_studio import estimate_weight
    except Exception:
        return 0
    return int(estimate_weight(item).get("weight_bytes") or 0)


def _context_of(item: Dict[str, Any]) -> int:
    for key in ("max_context_length", "max_context", "context_length", "context"):
        try:
            value = int(item.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def prepare_models(listed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chat models only, lightest weight first.

    Equal weights sort by maximum context, then by name.
    """
    rows: List[Dict[str, Any]] = []
    seen = set()
    for item in listed or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or item.get("key") or "").strip()
        if not model_id or model_id in seen or not _is_chat_model(item, model_id):
            continue
        seen.add(model_id)
        name = str(item.get("name") or item.get("display_name") or model_id)
        rows.append({
            "id": model_id,
            "name": name,
            "weight": _weight_of(item),
            "context": _context_of(item),
        })
    rows.sort(key=lambda row: (row["weight"], row["context"], row["name"].lower(), row["id"].lower()))
    return rows


def trim_edges(rows: List[Dict[str, Any]], fraction: float = 0.1) -> List[Dict[str, Any]]:
    """Drop the lightest and heaviest ``fraction`` before anonymous models are drawn."""
    count = len(rows)
    cut = int(math.floor(count * fraction))
    if cut <= 0 or count - (2 * cut) < 1:
        return list(rows)
    return list(rows[cut:count - cut])


def gaussian_count(pool: int, rng: random.Random) -> int:
    """How many anonymous analyzers. A gaussian centered on the middle of the pool."""
    if pool <= 0:
        return 0
    center = (1 + pool) / 2.0
    sigma = max(0.8, pool / 4.0)
    drawn = int(round(rng.gauss(center, sigma)))
    return max(0, min(pool, drawn))


def pick_anonymous(pool: List[Dict[str, Any]], count: int, rng: random.Random) -> List[Dict[str, Any]]:
    if count <= 0 or not pool:
        return []
    return list(rng.sample(list(pool), min(count, len(pool))))


def final_analyzer(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Heaviest model. Equal weight keeps the larger context, then the name."""
    if not rows:
        return None
    return max(rows, key=lambda row: (row["weight"], row["context"], row["name"].lower(), row["id"].lower()))


def provider_id_from(api: Any) -> str:
    """The provider Kerniq is actually using. Never a silent mock."""
    raw = ""
    if isinstance(api, dict):
        raw = str(api.get("provider") or "")
    else:
        raw = str(getattr(api, "provider", "") or "")
    raw = raw.strip()
    if not raw:
        raise RuntimeError(
            "Kerniq has no provider selected. Choose one in API & model and save before running the benchmark."
        )
    return raw


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def label_for(index: int) -> str:
    if 0 <= index < len(_LABELS):
        return _LABELS[index]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index < len(alphabet):
        return alphabet[index]
    return f"M{index + 1}"


def _status_penalty(status: str) -> int:
    if status == "timeout":
        return 25
    if status == "error":
        return 40
    if status == "load_failed":
        return 60
    return 0


def rank_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One row per model. The script owns the rank and the score. Models only comment."""
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        model = str(row.get("model") or "")
        item = grouped.setdefault(model, {
            "model": model,
            "status": "ok",
            "seconds": 0.0,
            "load_seconds": 0.0,
            "iterations": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "file_count": 0,
        })
        item["seconds"] = round(item["seconds"] + float(row.get("seconds") or 0), 2)
        item["load_seconds"] = round(max(item["load_seconds"], float(row.get("load_seconds") or 0)), 2)
        item["iterations"] += int(row.get("iterations") or 0)
        item["tool_calls"] += int(row.get("tool_calls") or 0)
        item["tool_errors"] += int(row.get("tool_errors") or 0)
        item["file_count"] += int(row.get("file_count") or 0)
        status = str(row.get("status") or "error")
        if status != "ok" and item["status"] == "ok":
            item["status"] = status

    def sort_key(item: Dict[str, Any]) -> tuple:
        status_rank = {"ok": 0, "timeout": 1, "error": 2, "load_failed": 3}.get(str(item["status"]), 2)
        return (status_rank, int(item["tool_errors"]), -int(item["file_count"]), float(item["seconds"]), str(item["model"]))

    ranked: List[Dict[str, Any]] = []
    for index, item in enumerate(sorted(grouped.values(), key=sort_key), start=1):
        penalty = _status_penalty(str(item["status"]))
        penalty += min(30, 5 * int(item["tool_errors"]))
        if item["status"] == "ok" and int(item["file_count"]) == 0:
            penalty += 10
        ranked.append({**item, "rank": index, "score": max(0, 100 - penalty)})
    return ranked


def anonymous_packet(runs: List[Dict[str, Any]], order: List[str], ranked: List[Dict[str, Any]]) -> str:
    """Facts and outputs for the analyzers. Model names stay out of this text."""
    label_of = {model: label_for(index) for index, model in enumerate(order)}
    lines = [
        "The ranking and every number below were computed by the benchmark script.",
        "Do not change them, do not invent a score, and do not guess which model wrote which output.",
        "Comment on the differences only.",
        "",
        "## Ranking",
    ]
    for row in ranked:
        label = label_of.get(str(row.get("model")), "?")
        lines.append(
            f"- {label}: rank {row['rank']}, score {row['score']}, status {row['status']}, "
            f"seconds {row['seconds']}, load_seconds {row['load_seconds']}, "
            f"iterations {row['iterations']}, tool_calls {row['tool_calls']}, "
            f"tool_errors {row['tool_errors']}, files {row['file_count']}"
        )
    lines.append("")
    for model in order:
        blocks = []
        for row in runs:
            if row.get("model") != model:
                continue
            blocks.append(
                f"### Slot {row.get('slot')} ({row.get('status')})\n\n{row.get('answer') or ''}"
            )
        lines.append(f"## Output {label_of[model]}\n\n" + "\n\n".join(blocks))
    return "\n\n".join(lines)


def render_full_report(ranked: List[Dict[str, Any]], runs: List[Dict[str, Any]]) -> str:
    lines = [
        "# Kerniq benchmark",
        "",
        "Ranks and scores are computed by this script. Analyzer models only comment and cannot change the numbers.",
        "",
        "| Rank | Model | Score | Status | Seconds | Load | Iterations | Tool calls | Tool errors | Files |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranked:
        lines.append(
            f"| {row['rank']} | `{row['model']}` | {row['score']} | {row['status']} | {row['seconds']} | "
            f"{row['load_seconds']} | {row['iterations']} | {row['tool_calls']} | {row['tool_errors']} | {row['file_count']} |"
        )
    lines.append("")
    lines.append("## Slots")
    lines.append("")
    for row in runs:
        lines.append(
            f"- `{row.get('model')}` slot {row.get('slot')}: {row.get('status')} "
            f"in {row.get('seconds')}s, iterations {row.get('iterations')}, "
            f"tool calls {row.get('tool_calls')}, tool errors {row.get('tool_errors')}, "
            f"files {row.get('file_count')}"
        )
    lines.append("")
    return "\n".join(lines)


def _project_files(root: Path) -> List[str]:
    if not root.is_dir():
        return []
    skip = {"__pycache__", ".git", ".kerniq-venv"}
    found: List[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip for part in path.parts):
            continue
        if path.name in {"result.md", "report.json", "REPORT.md"}:
            continue
        found.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(found)


def _run_metrics(context: Any, work: Path) -> Dict[str, Any]:
    from Kerniq.interfaces.models import MessageRole

    messages = list(getattr(context, "messages", None) or [])
    calls = 0
    errors = 0
    for msg in messages:
        role = getattr(msg, "role", None)
        if role == MessageRole.ASSISTANT:
            calls += len(getattr(msg, "tool_calls", None) or [])
        elif role == MessageRole.TOOL:
            low = str(getattr(msg, "content", "") or "").lower()
            if (
                low.startswith("execution error")
                or low.startswith("security error")
                or low.startswith("tool ")
                or "permission denied" in low
                or "timed out" in low
            ):
                errors += 1
    meta = getattr(context, "metadata", None) or {}
    files = _project_files(work)
    return {
        "iterations": int(meta.get("iterations_used") or 0),
        "tool_calls": calls,
        "tool_errors": errors,
        "files": files,
        "file_count": len(files),
        "outcome": str(meta.get("outcome") or ""),
    }


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="benchmark_pro",
            name="Model benchmark",
            version="1.1.0",
            api_version="1.0",
            manifest_version="1.0",
            entry_point="main.PluginImpl",
            description=(
                "Runs the selected provider's models one after another on up to three tasks, "
                "then asks anonymous analyzers and one main analyzer to write the report."
            ),
            capabilities=["tools"],
            author="Kerniq",
            license="MIT",
        )
        self._values: Dict[str, Any] = {}
        self._context: Optional[PluginContext] = None

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def settings_schema(self) -> SettingsSchema:
        fields = [
            SettingField(
                key="slot_count",
                label="Tasks",
                type=SettingType.INT,
                default=3,
                minimum=1,
                maximum=_MAX_SLOTS,
                description="How many tasks each model finishes before it is unloaded. The next model loads only after that.",
            ),
            SettingField(
                key="results_path",
                label="Results folder",
                type=SettingType.PATH,
                default="",
                description="Empty uses <workspace>/benchmarks. The folder must stay inside the workspace. Iterations, timeout, temperature and plan/act come from Kerniq settings, not from here.",
            ),
            SettingField(
                key="analyzer_system",
                label="Anonymous analyzer system prompt",
                type=SettingType.TEXT,
                default="You compare anonymous outputs labeled A, B, and C. The ranking was computed by the script. Do not change the numbers or guess model names.",
            ),
            SettingField(
                key="analyzer_task",
                label="Anonymous analyzer task",
                type=SettingType.TEXT,
                default="Comment on the anonymous outputs. Do not change the script ranking or invent a score.",
            ),
            SettingField(
                key="main_system",
                label="Main analyzer system prompt",
                type=SettingType.TEXT,
                default="You comment on the script's ranking. You do not recompute scores or change the order.",
            ),
            SettingField(
                key="main_task",
                label="Main analyzer task",
                type=SettingType.TEXT,
                default="Write a commentary: what was asked, how the outputs differ, and why the script's first place is or is not the most useful. Do not change the numbers.",
            ),
        ]
        for index in range(1, _MAX_SLOTS + 1):
            fields.append(SettingField(
                key=f"system_{index}",
                label=f"System prompt {index}",
                type=SettingType.TEXT,
                default="",
                description="Independent of the other slots. Empty means the model uses only the task.",
                group=f"slot_{index}",
                slot=index,
            ))
            fields.append(SettingField(
                key=f"task_{index}",
                label=f"Task {index}",
                type=SettingType.TEXT,
                default="",
                description="Independent task for this slot.",
                group=f"slot_{index}",
                slot=index,
            ))
        return SettingsSchema(
            component_id="benchmark_pro",
            component_type="plugin",
            title="Model benchmark",
            fields=fields,
        )

    def contributions(self) -> list:
        return [
            {
                "host": "plugin_web_ui",
                "slot": "settings",
                "id": "benchmark",
                "label": "Benchmark",
                "icon": "chart",
            },
            {
                "host": "plugin_web_ui",
                "slot": "panel",
                "id": "benchmark",
                "label": "Benchmark",
                "icon": "chart",
            },
        ]

    def actions(self) -> list:
        return [{
            "id": "run",
            "label": "Run benchmark",
            "description": "Run the configured tasks on each model, one model at a time.",
        }]

    async def run_action(self, action_id: str, tool_context: Any) -> Dict[str, Any]:
        if action_id != "run":
            raise ValueError(f"Unknown action {action_id}")
        return await self.run_benchmark(tool_context)

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if isinstance(values, dict):
            self._values = dict(values)

    async def initialize(self, context: PluginContext) -> bool:
        self._context = context
        return True

    async def shutdown(self) -> None:
        self._context = None

    def _ui(self, tool_context: Any):
        """Live Kerniq settings. Browser values on this run win over the file."""
        from Kerniq.settings.browser import overlay_settings
        from Kerniq.settings.loader import SettingsProvider
        from Kerniq.settings.ui_store import UiSettingsStore

        config = getattr(self._context, "config", None)
        state = getattr(getattr(config, "storage", None), "state_dir", None)
        if not state:
            state = SettingsProvider().config.storage.state_dir
        ui = UiSettingsStore(state).load()
        overlay = None
        if isinstance(tool_context, dict):
            overlay = tool_context.get("client_settings") or tool_context.get("ui")
        if isinstance(overlay, dict) and overlay:
            ui = overlay_settings(ui, overlay)
        return ui

    def _provider(self, ui):
        from Kerniq.models.factory import build_provider

        api = getattr(ui, "api", None)
        provider_id = provider_id_from(api)
        timeout = getattr(getattr(ui, "agent", None), "timeout_seconds", None)
        try:
            timeout = float(timeout) if timeout else 120.0
        except (TypeError, ValueError):
            timeout = 120.0
        if timeout <= 0:
            timeout = 120.0
        config = getattr(self._context, "config", None)
        return build_provider(provider_id, api=api, config=config, timeout=timeout), api, provider_id

    def _active_path(self, workspace: Path) -> Path:
        return (workspace / "benchmarks" / "active.json").resolve()

    def _write_state(self, run_dir: Path, workspace: Path, state: Dict[str, Any]) -> None:
        state = dict(state)
        state["pid"] = os.getpid()
        state["updated"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(state, ensure_ascii=False, indent=2)
        (run_dir / "state.json").write_text(text, encoding="utf-8")
        active = self._active_path(workspace)
        active.parent.mkdir(parents=True, exist_ok=True)
        active.write_text(text, encoding="utf-8")

    def _assert_idle(self, workspace: Path) -> None:
        active = self._active_path(workspace)
        if not active.is_file():
            return
        try:
            state = json.loads(active.read_text(encoding="utf-8"))
        except Exception:
            return
        if str(state.get("status") or "") != "running":
            return
        if _pid_alive(int(state.get("pid") or 0)):
            raise RuntimeError("A benchmark is already running. Leave it; it keeps going in the background.")

    async def run_benchmark(self, tool_context: Any, *, task_override: str = "") -> Dict[str, Any]:
        if not _BENCH_LOCK.acquire(blocking=False):
            raise RuntimeError("A benchmark is already running. Leave it; it keeps going in the background.")
        run_dir: Optional[Path] = None
        workspace: Optional[Path] = None
        try:
            values = dict(self._values)
            if task_override:
                values["task"] = task_override
                if not _text(values, "task_1"):
                    values["task_1"] = task_override
            slots = slots_from(values)
            if not slots:
                raise ValueError("Benchmark task is empty.")
            workspace = workspace_root(tool_context)
            self._assert_idle(workspace)
            folder = results_dir(workspace, _text(values, "results_path"))
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            run_dir = folder / stamp
            run_dir.mkdir(parents=True, exist_ok=True)
            ui = self._ui(tool_context)
            from Kerniq.interfaces.models import GenerationOptions
            self._gen_options = GenerationOptions(
                temperature=float(ui.api.temperature if ui.api.temperature is not None else 0.7),
                max_tokens=ui.api.max_tokens,
                top_p=float(ui.agent.top_p if ui.agent.top_p is not None else 1.0),
                streaming=False,
            )
            self._acquire_file_lock(workspace)
            provider, api, provider_id = self._provider(ui)
            try:
                listed = await provider.list_models() if hasattr(provider, "list_models") else []
            except Exception as exc:
                raise RuntimeError(f"Could not list models from {provider_id}: {exc}") from exc
            catalog = prepare_models(listed if isinstance(listed, list) else [])
            if not catalog and provider_id in {"mock", "mock_provider"}:
                catalog = [{"id": "mock", "name": "mock", "weight": 0, "context": 0}]
            if not catalog:
                raise RuntimeError(f"Provider {provider_id} returned no chat models.")
            models = [row["id"] for row in catalog]
            self._write_state(run_dir, workspace, {
                "status": "running",
                "phase": "starting",
                "provider": provider_id,
                "folder": str(run_dir),
                "models": models,
                "index": 0,
                "total": len(models),
                "model": "",
                "slot": 0,
                "slots": len(slots),
                "error": "",
            })
            runs: List[Dict[str, Any]] = []
            analyses: List[str] = []
            try:
                for index, row in enumerate(catalog, start=1):
                    model_id = row["id"]
                    self._write_state(run_dir, workspace, {
                        "status": "running",
                        "phase": "loading",
                        "provider": provider_id,
                        "folder": str(run_dir),
                        "models": models,
                        "index": index,
                        "total": len(models),
                        "model": model_id,
                        "slot": 0,
                        "slots": len(slots),
                        "error": "",
                    })
                    switched = await self._switch_model(provider, api, model_id)
                    model_rows: List[Dict[str, Any]] = []
                    if not switched["ok"]:
                        for slot_index, slot in enumerate(slots, start=1):
                            model_rows.append(self._empty_row(
                                model_id, slot_index, slot, "load_failed", switched["error"], switched["seconds"]
                            ))
                    else:
                        for slot_index, slot in enumerate(slots, start=1):
                            self._write_state(run_dir, workspace, {
                                "status": "running",
                                "phase": "task",
                                "provider": provider_id,
                                "folder": str(run_dir),
                                "models": models,
                                "index": index,
                                "total": len(models),
                                "model": model_id,
                                "slot": slot_index,
                                "slots": len(slots),
                                "error": "",
                            })
                            one = await self._run_one(
                                provider, workspace, run_dir, model_id, slot_index, slot, ui
                            )
                            one["load_seconds"] = switched["seconds"] if slot_index == 1 else 0
                            model_rows.append(one)
                    # The model finished every task. Unload it and prove it is gone
                    # before the next catalog model — including a model the user had loaded.
                    try:
                        await self._quiesce(provider, api)
                    except Exception as exc:
                        logger.exception("unload after %s failed", model_id)
                        for item in model_rows:
                            if item.get("status") == "ok":
                                item["status"] = "error"
                                item["error"] = f"Unload was not confirmed: {exc}"
                        self._write_model_report(run_dir, model_id, model_rows)
                        runs.extend(model_rows)
                        raise
                    self._write_model_report(run_dir, model_id, model_rows)
                    runs.extend(model_rows)
                ranked = rank_rows(runs)
                key = {label_for(index): model for index, model in enumerate(models)}
                (run_dir / "key.json").write_text(
                    json.dumps({"models": key, "slots": slots, "order": models}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (run_dir / "FULL_BENCHMARK_REPORT.md").write_text(
                    render_full_report(ranked, runs),
                    encoding="utf-8",
                )
                self._write_state(run_dir, workspace, {
                    "status": "running",
                    "phase": "analysis",
                    "provider": provider_id,
                    "folder": str(run_dir),
                    "models": models,
                    "index": len(models),
                    "total": len(models),
                    "model": "",
                    "slot": 0,
                    "slots": len(slots),
                    "error": "",
                })
                analyses = await self._analyze(provider, api, run_dir, runs, values, catalog, ranked)
            finally:
                try:
                    await self._quiesce(provider, api)
                except Exception:
                    logger.exception("final unload failed")
            report = {
                "folder": str(run_dir),
                "provider": provider_id,
                "models": models,
                "runs": runs,
                "ranking": [
                    {k: row[k] for k in ("rank", "model", "score", "status", "seconds", "iterations", "tool_calls", "tool_errors", "file_count")}
                    for row in rank_rows(runs)
                ],
                "analyses": analyses,
            }
            (run_dir / "summary.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._write_state(run_dir, workspace, {
                "status": "done",
                "phase": "done",
                "provider": provider_id,
                "folder": str(run_dir),
                "models": models,
                "index": len(models),
                "total": len(models),
                "model": "",
                "slot": 0,
                "slots": len(slots),
                "error": "",
            })
            return report
        except Exception as exc:
            if run_dir is not None and workspace is not None:
                self._write_state(run_dir, workspace, {
                    "status": "failed",
                    "phase": "failed",
                    "provider": "",
                    "folder": str(run_dir),
                    "model": "",
                    "error": str(exc),
                })
            raise
        finally:
            self._release_file_lock()
            _BENCH_LOCK.release()

    def _acquire_file_lock(self, workspace: Path) -> None:
        path = workspace / "benchmarks" / ".run.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        for _attempt in range(2):
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    pid = int((path.read_text(encoding="utf-8") or "0").strip() or "0")
                except Exception:
                    pid = 0
                if _pid_alive(pid):
                    raise RuntimeError(
                        "A benchmark is already running. Leave it; it keeps going in the background."
                    )
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
                continue
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self._lock_path = path
            return
        raise RuntimeError("Could not lock the benchmark run.")

    def _release_file_lock(self) -> None:
        path = getattr(self, "_lock_path", None)
        self._lock_path = None
        if path is None:
            return
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            logger.exception("could not release benchmark lock")

    async def _quiesce(self, provider, api) -> None:
        """Unload every model and do not return until the catalog says nothing is loaded."""
        provider_id = str(getattr(api, "provider", "") or getattr(provider, "provider_id", "") or "")
        if provider_id != "lm_studio" or not hasattr(provider, "unload_all"):
            return
        try:
            from Kerniq.models.providers.lm_studio import _invalidate_model_cache
        except Exception:
            _invalidate_model_cache = None
        last: List[Any] = []
        for _attempt in range(8):
            if _invalidate_model_cache is not None:
                _invalidate_model_cache()
            try:
                await provider.unload_all()
            except Exception:
                logger.exception("unload_all failed")
            try:
                last = await provider.loaded_instances() if hasattr(provider, "loaded_instances") else []
            except Exception:
                logger.exception("loaded instance check failed")
                last = [{"id": "?"}]
            if not last:
                return
            await asyncio.sleep(0.45)
        names = []
        for item in last or []:
            if isinstance(item, dict):
                names.append(str(item.get("model") or item.get("id") or item.get("instance_id") or "?"))
            else:
                names.append(str(item))
        raise RuntimeError("Previous model is still loaded: " + ", ".join(names))

    async def _switch_model(self, provider, api, model_id: str) -> Dict[str, Any]:
        """Unload whatever is loaded, confirm it, then load this model alone."""
        started = time.monotonic()
        provider_id = str(getattr(api, "provider", "") or getattr(provider, "provider_id", "") or "")
        if provider_id != "lm_studio":
            if hasattr(provider, "model"):
                provider.model = model_id
            return {"ok": True, "seconds": round(time.monotonic() - started, 2), "error": ""}
        try:
            await self._quiesce(provider, api)
            if not hasattr(provider, "load_model"):
                raise RuntimeError("This LM Studio provider cannot load a model.")
            await provider.load_model(model_id)
            if hasattr(provider, "model_is_loaded"):
                loaded = await provider.model_is_loaded(model_id)
                if not loaded:
                    raise RuntimeError(f"{model_id} did not stay loaded")
            if hasattr(provider, "model"):
                provider.model = model_id
        except Exception as exc:
            logger.exception("could not load %s", model_id)
            return {"ok": False, "seconds": round(time.monotonic() - started, 2), "error": str(exc)}
        return {"ok": True, "seconds": round(time.monotonic() - started, 2), "error": ""}

    async def _exclusive_unload(self, provider, api) -> None:
        await self._quiesce(provider, api)

    @staticmethod
    def _empty_row(model_id, slot_index, slot, status, error, seconds) -> Dict[str, Any]:
        return {
            "model": model_id,
            "slot": slot_index,
            "status": status,
            "seconds": seconds,
            "load_seconds": seconds,
            "iterations": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "file_count": 0,
            "files": [],
            "outcome": status,
            "path": "",
            "answer": error,
            "error": error,
            "task": slot.get("task") or "",
        }

    def _write_model_report(self, run_dir: Path, model_id: str, rows: List[Dict[str, Any]]) -> None:
        safe_model = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in model_id)[:80]
        folder = run_dir / safe_model
        folder.mkdir(parents=True, exist_ok=True)
        payload = {"model": model_id, "slots": rows}
        (folder / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        lines = [f"# {model_id}", ""]
        for row in rows:
            lines.append(
                f"- slot {row['slot']}: {row['status']} in {row['seconds']}s, "
                f"iterations {row['iterations']}, tool calls {row['tool_calls']}, "
                f"tool errors {row['tool_errors']}, files {row['file_count']}"
            )
            if row.get("error"):
                lines.append(f"  - {row['error']}")
        lines.append("")
        (folder / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    def _arm_agent(self, agent, registry, ui) -> bool:
        """Copy Kerniq's agent, sampling and plan settings. Slot prompts stay the plugin's."""
        from Kerniq.core.runtime_flow import apply_runtime, compose_plan_allowed

        apply_runtime(agent.orchestrator, ui)
        compose = bool(getattr(ui.chat, "compose_plan", False)) and compose_plan_allowed(registry)
        agent.orchestrator.compose_plan = compose
        agent.orchestrator.finish_open_plan = False
        if getattr(ui.agent, "max_iterations", None) is not None:
            agent.orchestrator.max_iterations = int(ui.agent.max_iterations)
        top_p = getattr(ui.agent, "top_p", None)
        options = agent.orchestrator.generation_options
        agent.orchestrator.generation_options = options.model_copy(update={
            "top_p": float(top_p if top_p is not None else 1.0),
            "streaming": False,
        })
        agent.response_language = str(getattr(ui.chat, "response_language", None) or "auto")
        return compose

    async def _run_one(self, provider, workspace, run_dir, model_id, slot_index, slot, ui) -> Dict[str, Any]:
        from Kerniq.assembly import build_tool_registry
        from Kerniq.core.runtime_flow import act_followup_task, handoff_archive, plan_research_record, route_mode
        from Kerniq.interfaces.models import MessageRole
        from Kerniq.settings.loader import SettingsProvider

        safe_model = "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in model_id)[:80]
        work = run_dir / safe_model / f"slot-{slot_index}"
        work.mkdir(parents=True, exist_ok=True)
        config = getattr(self._context, "config", None) or SettingsProvider().config
        state = getattr(getattr(config, "storage", None), "state_dir", None) or (workspace / "state")
        registry, _policy = build_tool_registry(work, config=config, state_dir=state)
        agent = Agent(provider, registry)
        compose = self._arm_agent(agent, registry, ui)
        task = slot.get("task") or ""
        system = slot.get("system") or ""
        if compose:
            system = (system + "\n\nUntil a TODO exists, the first turn is update_plan and nothing else.").strip()
        mode = "act"
        if bool(getattr(ui.chat, "mode_auto", False)):
            mode = await route_mode(provider, task, compose_plan=compose)
        else:
            mode = "plan" if str(getattr(ui.chat, "agent_mode", "") or "act").lower() == "plan" else "act"
        auto_act = bool(getattr(ui.chat, "auto_act_after_plan", False))
        started = time.monotonic()
        status = "ok"
        text = ""
        try:
            text = await agent.run(
                task,
                workspace=str(work),
                system_prompt=system or None,
                response_language=agent.response_language,
                agent_mode=mode,
                plan_gate=compose,
                plan_handoff=bool(mode == "plan" and auto_act and compose),
            )
            outcome = ""
            if agent.last_context is not None:
                outcome = str((agent.last_context.metadata or {}).get("outcome") or "")
            failed = outcome in _FAIL_OUTCOMES
            open_items = []
            if agent.last_context is not None:
                raw_plan = (agent.last_context.metadata or {}).get("plan") or []
                open_items = [
                    item for item in raw_plan
                    if isinstance(item, dict) and item.get("status") not in ("done", "skipped", "failed")
                ]
            if mode == "plan" and auto_act and compose and not failed and not open_items:
                draft = plan_research_record(
                    agent.last_context.messages if agent.last_context is not None else [],
                    text if isinstance(text, str) else "",
                )
                research = handoff_archive(agent.last_context)
                follow = act_followup_task(task, draft, max_iterations=agent.orchestrator.max_iterations)
                hist = []
                if agent.last_context is not None:
                    hist = [msg for msg in agent.last_context.messages if getattr(msg, "role", None) != MessageRole.SYSTEM]
                text = await agent.run(
                    task,
                    workspace=str(work),
                    system_prompt=(system + "\n\n" + follow).strip(),
                    history=hist or None,
                    response_language=agent.response_language,
                    agent_mode="act",
                    plan_gate=False,
                    plan_archive=research or None,
                )
        except Exception as exc:
            status = "error"
            text = str(exc)
            logger.exception("model %s slot %s failed", model_id, slot_index)
        seconds = round(time.monotonic() - started, 2)
        metrics = _run_metrics(getattr(agent, "last_context", None), work)
        if status == "ok" and metrics.get("outcome") in _FAIL_OUTCOMES:
            status = "error"
        body = (
            f"# {model_id} / slot {slot_index}\n\n"
            f"status: {status}\nseconds: {seconds}\nmode: {mode}\n"
            f"iterations: {metrics['iterations']}\ntool_calls: {metrics['tool_calls']}\n"
            f"tool_errors: {metrics['tool_errors']}\nfiles: {metrics['file_count']}\n\n"
            f"## System\n\n{system or '(none)'}\n\n"
            f"## Task\n\n{task}\n\n"
            f"## Answer\n\n{text}\n"
        )
        (work / "result.md").write_text(body, encoding="utf-8")
        return {
            "model": model_id,
            "slot": slot_index,
            "status": status,
            "seconds": seconds,
            "load_seconds": 0,
            "path": str(work / "result.md"),
            "answer": str(text)[:8000],
            "task": task,
            "mode": mode,
            **metrics,
        }

    async def _analyze(self, provider, api, run_dir, runs, values, catalog, ranked) -> List[str]:
        analysis_dir = run_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        order = [row["id"] for row in catalog]
        facts = []
        for index, model in enumerate(order):
            row = next((item for item in ranked if item["model"] == model), None)
            if row is None:
                continue
            facts.append({
                "label": label_for(index),
                "rank": row["rank"],
                "score": row["score"],
                "status": row["status"],
                "seconds": row["seconds"],
                "load_seconds": row["load_seconds"],
                "iterations": row["iterations"],
                "tool_calls": row["tool_calls"],
                "tool_errors": row["tool_errors"],
                "file_count": row["file_count"],
            })
        (analysis_dir / "FACTS.json").write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
        (analysis_dir / "RANKING.json").write_text(
            json.dumps({"computed_by": "script", "rows": facts}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        written = [str(analysis_dir / "FACTS.json"), str(analysis_dir / "RANKING.json")]
        if not runs or not catalog:
            return written
        pool = trim_edges(catalog, 0.1)
        rng = random.Random()
        count = gaussian_count(len(pool), rng)
        chosen = pick_anonymous(pool, count, rng)
        final = final_analyzer(catalog)
        (analysis_dir / "selection.json").write_text(json.dumps({
            "anonymous_count": count,
            "anonymous": [row["id"] for row in chosen],
            "pool": [row["id"] for row in pool],
            "final": final["id"] if final else "",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        packet = anonymous_packet(runs, order, ranked)
        system = _text(values, "analyzer_system") or "Compare the anonymous outputs. Do not change the script ranking."
        task = _text(values, "analyzer_task") or "Comment on the outputs. Do not change the numbers."
        notes = []
        for index, row in enumerate(chosen, start=1):
            switched = await self._switch_model(provider, api, row["id"])
            if not switched["ok"]:
                text = f"Analyzer was not loaded: {switched['error']}"
            else:
                text = await self._ask(provider, system, task + "\n\n" + packet)
            path = analysis_dir / f"anonymous-{index}.md"
            path.write_text(text, encoding="utf-8")
            written.append(str(path))
            notes.append(f"## Analyzer {label_for(index - 1)}\n\n{text}")
            try:
                await self._quiesce(provider, api)
            except Exception as exc:
                logger.exception("analyzer unload failed")
                notes.append(f"Unload was not confirmed: {exc}")
        if final is None:
            return written
        switched = await self._switch_model(provider, api, final["id"])
        main_system = _text(values, "main_system") or "Write a commentary. Do not change the script ranking or the numbers."
        main_task = _text(values, "main_task") or "Comment on the ranking. Do not recompute it."
        if not switched["ok"]:
            report = f"Main analyzer was not loaded: {switched['error']}"
        else:
            report = await self._ask(
                provider, main_system, main_task + "\n\n" + packet + "\n\n" + "\n\n".join(notes)
            )
        path = analysis_dir / "report.md"
        path.write_text(report, encoding="utf-8")
        written.append(str(path))
        try:
            await self._quiesce(provider, api)
        except Exception:
            logger.exception("final analyzer unload failed")
        return written

    async def _ask(self, provider, system: str, user: str) -> str:
        from Kerniq.interfaces.models import GenerationOptions

        options = getattr(self, "_gen_options", None) or GenerationOptions(streaming=False)
        if getattr(options, "streaming", False):
            options = options.model_copy(update={"streaming": False})
        request = ModelRequest(
            messages=[
                Message(role=MessageRole.SYSTEM, content=system),
                Message(role=MessageRole.USER, content=user[:24000]),
            ],
            session_id=uuid4(),
            tools=None,
            options=options,
        )
        try:
            response = await provider.generate(request)
        except Exception as exc:
            logger.exception("analyzer call failed")
            return f"Analyzer failed: {exc}"
        messages = getattr(response, "messages", None) or []
        if not messages:
            return ""
        return str(messages[-1].content or "")

