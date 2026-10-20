"""Shared run policy for the CLI and the UI shell.

The UI does not own these decisions. It only displays what this module does.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from Kerniq.interfaces.models import GenerationOptions, Message, MessageRole, ModelRequest

logger = logging.getLogger(__name__)

_OVERFLOW_MARKERS = (
    "context length",
    "maximum context",
    "context window",
    "context_length_exceeded",
    "too many tokens",
    "prompt is too long",
    "input is too long",
    "exceeds the context",
    "exceeds the model's context",
    "n_ctx",
    "tokens to keep",
    "requested tokens exceed",
)


def is_context_overflow(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _OVERFLOW_MARKERS)


def apply_runtime(orchestrator, ui) -> None:
    """Copy agent/api/chat limits onto the orchestrator. None max_tokens means no cap."""
    agent = ui.agent
    api = ui.api
    chat = ui.chat
    if getattr(agent, "max_iterations", None) is not None:
        orchestrator.max_iterations = int(agent.max_iterations)
    retries = int(getattr(agent, "loop_retries", None) or 4)
    orchestrator.max_content_loop_hits = max(1, retries)
    orchestrator.max_identical_tool_streak = max(2, retries)
    orchestrator.max_plan_continuations = max(1, retries)
    orchestrator.finish_open_plan = True
    orchestrator.generation_options = GenerationOptions(
        temperature=api.temperature if api.temperature is not None else 0.7,
        max_tokens=api.max_tokens,
        streaming=bool(getattr(chat, "streaming", False)),
    )


async def probe_context_limit(provider, model: str) -> int:
    want = (model or "").strip()
    try:
        models = await provider.list_models() if hasattr(provider, "list_models") else []
    except Exception:
        return 0
    loaded_fallback = 0
    for item in models or []:
        mid = str(item.get("id") or item.get("key") or "")
        if "embed" in mid.lower():
            continue
        limit = (
            item.get("loaded_context_length")
            or item.get("context_length")
            or item.get("max_context_length")
            or item.get("context")
        )
        if item.get("loaded_context_length"):
            loaded_fallback = int(item["loaded_context_length"])
        if not limit:
            continue
        if want and (mid == want or want in mid or mid in want):
            return int(limit)
    return int(loaded_fallback or 0)


async def use_model_for_mode(provider, api, mode: str) -> Optional[str]:
    """Point the provider at the model for this mode.

    Plan uses ``api.model``. Act uses ``api.act_model`` when split models
    are on, otherwise the same model. Shells call this and only display
    the result. Returns an error string, or None when the switch worked
    or was not needed.
    """
    plan_model = str(getattr(api, "model", "") or "").strip()
    act_model = str(getattr(api, "act_model", "") or "").strip()
    split = bool(getattr(api, "split_models", False))
    target = act_model if mode == "act" and split and act_model else plan_model
    if not target:
        return None
    current = str(getattr(provider, "model", "") or "").strip()
    if current == target:
        return None
    provider_id = str(getattr(api, "provider", "") or getattr(provider, "provider_id", "") or "")
    try:
        if provider_id == "lm_studio" and hasattr(provider, "unload_all") and hasattr(provider, "load_model"):
            await provider.unload_all()
            await provider.load_model(target)
        elif provider_id == "ollama":
            import httpx

            base = str(getattr(provider, "base_url", "") or getattr(api, "base_url", "") or "http://127.0.0.1:11434").rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            async with httpx.AsyncClient(timeout=30) as client:
                if current:
                    await client.post(base + "/api/generate", json={"model": current, "keep_alive": 0})
                await client.post(base + "/api/generate", json={"model": target, "keep_alive": "10m"})
        if hasattr(provider, "model"):
            provider.model = target
        logger.info("Model for %s mode is %s", mode, target)
        return None
    except Exception as exc:
        logger.exception("model switch failed")
        return str(exc)


async def route_mode(provider, task: str, *, compose_plan: bool) -> str:
    """Ask the model whether the request needs a research plan. Core, not the UI.

    A thinking model often leaves the word in reasoning and the content empty.
    An empty or unclear verdict is ACT. Reading, reviewing, and finding bugs
    are ACT even when they open many files.
    """
    if not compose_plan:
        return "act"
    request = ModelRequest(
        messages=[
            Message(
                role=MessageRole.SYSTEM,
                content=(
                    "You route one user request. Reply with a single word: PLAN or ACT. "
                    "ACT if the user wants an answer, a review, a bug list, an explanation, "
                    "a summary, or one change. Reading or searching many files is still ACT. "
                    "PLAN only if the user wants a design or a multi-step implementation "
                    "that must be studied before any file is changed. "
                    "If unsure, reply ACT. Do not explain."
                ),
            ),
            Message(role=MessageRole.USER, content=(task or "")[:4000]),
        ],
        session_id=uuid4(),
        tools=None,
        options=GenerationOptions(
            temperature=0,
            max_tokens=16,
            streaming=False,
            extra_params={"enable_thinking": False, "thinking": {"type": "disabled"}, "reasoning_effort": "none"},
        ),
        metadata={"kerniq_internal": "route"},
    )
    try:
        response = await provider.generate(request)
    except Exception:
        logger.exception("plan/act verdict failed")
        return "act"
    verdict = route_word(response)
    if verdict == "PLAN":
        return "plan"
    return "act"


def route_word(response) -> str:
    """Last standalone PLAN or ACT in content or reasoning. Empty if neither."""
    import re

    chunks: list[str] = []
    if response is not None:
        for msg in getattr(response, "messages", None) or []:
            chunks.append(getattr(msg, "content", None) or "")
            meta = getattr(msg, "metadata", None) or {}
            if isinstance(meta, dict) and meta.get("reasoning"):
                chunks.append(str(meta.get("reasoning")))
        meta = getattr(response, "metadata", None) or {}
        if isinstance(meta, dict) and meta.get("reasoning"):
            chunks.append(str(meta.get("reasoning")))
    hits = re.findall(r"\b(PLAN|ACT)\b", "\n".join(chunks).upper())
    return hits[-1] if hits else ""


def promote_reasoning(response) -> bool:
    """Copy a long reasoning trace into empty assistant content.

    Thinking models leave the actual reply in reasoning and content blank.
    That used to be stored as an empty finish and the answer was dropped.
    """
    if response is None:
        return False
    meta = getattr(response, "metadata", None) or {}
    fallback = str(meta.get("reasoning") or "").strip() if isinstance(meta, dict) else ""
    changed = False
    for msg in getattr(response, "messages", None) or []:
        if getattr(msg, "tool_calls", None):
            continue
        if (getattr(msg, "content", None) or "").strip():
            continue
        reasoning = ""
        msg_meta = getattr(msg, "metadata", None) or {}
        if isinstance(msg_meta, dict):
            reasoning = str(msg_meta.get("reasoning") or "").strip()
        if len(reasoning) < 80:
            reasoning = fallback if len(fallback) >= 80 else ""
        if len(reasoning) < 80:
            continue
        msg.content = reasoning
        changed = True
    return changed


def extract_draft(text: str, *, strict: bool = False) -> str:
    raw = text or ""
    start = raw.find("===ACT_DRAFT===")
    end = raw.find("===END_DRAFT===")
    if start >= 0 and end > start:
        return raw[start + len("===ACT_DRAFT==="):end].strip()
    if strict:
        return ""
    prose = raw.split("===ACT_DRAFT===")[0].strip()
    return prose[:4000]


def strip_draft(text: str) -> str:
    raw = text or ""
    start = raw.find("===ACT_DRAFT===")
    if start < 0:
        return raw.strip()
    return raw[:start].strip()


def plan_research_record(messages, final: str = "") -> str:
    """What Act actually needs from Plan.

    The archived TODO is only titles. The audit is often written before the
    list exists, so the last message alone is not the research. Prefer a real
    ACT_DRAFT, and keep earlier findings when that block is missing or thin.
    """
    drafts: list[str] = []
    prose: list[str] = []
    seen = set()
    rows = list(messages or [])
    if final:
        rows.append(Message(role=MessageRole.ASSISTANT, content=final))
    for msg in rows:
        if getattr(msg, "role", None) != MessageRole.ASSISTANT:
            continue
        text = (msg.content or "").strip()
        if not text or text.startswith("[kerniq]"):
            continue
        drafted = extract_draft(text, strict=True)
        if drafted and drafted not in seen:
            seen.add(drafted)
            drafts.append(drafted)
        clean = strip_draft(text)
        if clean and "===ACT_DRAFT===" not in text and clean not in seen:
            seen.add(clean)
            prose.append(clean)
    notes = "\n\n".join(prose).strip()
    if len(notes) > 14000:
        notes = notes[:7000] + "\n\n…[middle omitted]…\n\n" + notes[-7000:]
    if drafts:
        body = drafts[-1]
        if len(body) < 400 and notes and notes not in body:
            return body + "\n\nEarlier findings from the same plan run:\n" + notes
        return body
    if not notes:
        return ""
    return (
        "Plan mode did not write an ACT_DRAFT. "
        "These are the findings it did write. Use them. Do not redo the reading just to rediscover them.\n\n"
        + notes
    )


def act_followup_task(user_task: str, draft: str, *, max_iterations: int) -> str:
    return (
        "You are in ACT. Plan mode is finished and its iteration budget does not carry over. "
        f"Yours starts at zero (limit {max_iterations}). Context compaction does not spend iterations.\n"
        "The plan-mode transcript was cleared on purpose. "
        "The text under Draft is the research. The archived TODO is only titles of finished lookups. "
        "Do not treat those titles as the audit, and do not copy them onto your TODO.\n"
        "First write YOUR OWN action TODO with update_plan, before any other tool, from the original request and then from the draft. "
        "You may search more after that list exists. Insert new items only among the current item and the items after it. "
        "Do not delete items or rename existing ones. "
        "Statuses: pending, active, done, frozen, failed. "
        "A failed archive item is a lookup Plan already exhausted. Do not repeat it unless the draft says the fact is still required. "
        "Mark your own item failed only after the same attempt is empty about three times, or you have given up. Not on the first miss. "
        "failed stays on the list and does not block the end. frozen still does. "
        "You cannot finish, refuse, or abandon the task while any item is pending, active, or frozen.\n\n"
        "Draft from plan mode:\n"
        + (draft or "(no draft)")
        + "\n\nOriginal request:\n"
        + (user_task or "")
    )


def open_plan_items(context) -> list:
    if context is None:
        return []
    raw = (context.metadata or {}).get("plan") or []
    if not isinstance(raw, list):
        return []
    return [
        item for item in raw
        if isinstance(item, dict) and str(item.get("status") or "") not in ("done", "skipped", "failed")
    ]


def handoff_archive(context) -> list:
    """Closed Plan items kept for Act. Ids are namespaced so Act can number from 1.

    The archive is memory of finished research. It is not Act's live TODO.
    """
    if context is None:
        return []
    meta = getattr(context, "metadata", None) or {}
    rows = []
    seen = set()
    for source in (meta.get("plan_archive") or [], meta.get("plan") or []):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "")
            if status not in ("done", "skipped", "failed"):
                continue
            item_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip()
            if not item_id or not title:
                continue
            if not item_id.startswith("research:"):
                item_id = "research:" + item_id
            if item_id in seen:
                continue
            seen.add(item_id)
            rows.append({"id": item_id, "title": title, "status": status})
    return rows


async def attach_compactor(orchestrator, workspace_config) -> None:
    """Load the compaction plugin when it is installed. Absence is not an error."""
    try:
        from Kerniq.plugins.manager import PluginManager
        from Kerniq.plugins.base import PluginContext
        from Kerniq.devtools.paths import find_plugins_dirs

        def _ctx():
            return PluginContext(
                logger=logger,
                config=workspace_config,
                event_bus=None,
                tool_registry=None,
            )

        manager = PluginManager(_ctx)
        for plugin_dir in find_plugins_dirs():
            await manager.discover_and_load(plugin_dir, skip_ids=["plugin_web_ui"])
        compactor = manager.plugins.get("plugin_context_compact")
        if compactor is not None and getattr(compactor, "cfg_enabled", True):
            orchestrator.compactor = compactor
    except Exception:
        logger.info("No compaction plugin. The core will trim the window itself.")


def system_prompt_from_settings(ui, tool_names: list[str]) -> Optional[str]:
    system = (ui.prompt.system_prompt or "").strip() or None
    if getattr(ui.prompt, "include_tool_catalog", True) and tool_names:
        catalog = ", ".join(tool_names)
        system = ((system or "") + f"\n\nAvailable tools: {catalog}.").strip()
    return system
