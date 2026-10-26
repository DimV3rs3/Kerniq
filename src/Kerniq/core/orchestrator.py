import asyncio
import contextlib
import json
import logging
from pathlib import Path
import tomllib
from typing import Any, Optional
from .context import TaskContext
from ..interfaces.models import ModelRequest, ModelResponse, Message, MessageRole, GenerationOptions
from ..interfaces.providers import ModelProvider
from ..interfaces.errors import ProviderError, ErrorCode
from ..tools.registry import ToolRegistry
from ..tools.validate_args import argument_error
from ..security.policy import SecurityPolicy, PolicyDecision
from ..security.task_scope import use_task
from .verifier import Verifier, is_unverified

logger = logging.getLogger(__name__)


class _RunStopped(Exception):
    """User stop aborted the current model call or tool."""


def _spec_name(spec) -> str:
    if not isinstance(spec, dict):
        return ""
    fn = spec.get("function") if isinstance(spec.get("function"), dict) else None
    if fn and fn.get("name"):
        return str(fn.get("name"))
    return str(spec.get("name") or "")


def _plan_status_blocks(status: object) -> bool:
    """Pending, active, and frozen hold the run. Failed is a recorded miss."""
    text = str(status or "pending").strip().lower().replace(" ", "_")
    return text not in ("done", "skipped", "failed", "complete", "completed", "skip", "cancelled", "canceled")


class Orchestrator:
    def __init__(self, provider: ModelProvider, tool_registry: ToolRegistry, 
                 security_policy: Optional[SecurityPolicy] = None, 
                 verifier: Optional[Verifier] = None,
                 approval_provider: Optional[Any] = None):
        self.provider = provider
        self.tool_registry = tool_registry
        self.security_policy = security_policy
        self.verifier = verifier
        self.approval_provider = approval_provider
        self.max_iterations = 10
        self.max_identical_tool_streak = 3
        self.max_empty_retries = 2
        self.provider_retries = 2
        self.max_verification_retries = 2
        self.max_content_loop_hits = 2
        self.max_plan_continuations = 2
        self.finish_open_plan = False
        # A TODO is required only when the operator turned "Build a plan" on.
        self.compose_plan = False
        self.generation_options = GenerationOptions()
        self.compactor = None
        self.on_progress = None
        self.on_plan = None
        self.require_plan = True
        # Kept so a recovered text call can be observed. It must not turn the
        # native tools array off: that array is what LM Studio's template uses.
        self._text_only_models: set[str] = set()


    def _state_dir(self):
        try:
            from Kerniq.settings.loader import SettingsProvider

            return SettingsProvider().config.storage.state_dir
        except Exception:
            return None

    def _model_needs_text_tools(self, model_id: str) -> bool:
        """Native tools stay on for every model.

        LM Studio injects the ``tools`` array through the model's own chat
        template and parses the call that template trained. Dropping the array
        after an empty reply, or because ``native_tools`` was saved as false,
        makes the same model write a call as plain text.
        """
        del model_id
        return False

    def _mark_text_only(self, model_id: str, *, persist: bool) -> None:
        if not model_id:
            return
        self._text_only_models.add(model_id)
        if not persist:
            return
        from Kerniq.models.capabilities import remember_native_tools

        remember_native_tools(self._state_dir(), model_id, False)

    def _known_tool_names(self) -> set[str]:
        registry = self.tool_registry
        if registry is None or not hasattr(registry, "list_tools"):
            return set()
        try:
            tools = registry.agent_tools() if hasattr(registry, "agent_tools") else (registry.list_tools() or [])
        except Exception:
            return set()
        return {str(tool.name) for tool in tools if getattr(tool, "name", None)}

    def _known_tool_schemas(self) -> dict:
        registry = self.tool_registry
        if registry is None or not hasattr(registry, "list_tools"):
            return {}
        try:
            tools = registry.agent_tools() if hasattr(registry, "agent_tools") else (registry.list_tools() or [])
        except Exception:
            return {}
        schemas = {}
        for tool in tools:
            name = getattr(tool, "name", None)
            schema = getattr(tool, "input_schema", None)
            props = schema.get("properties") if isinstance(schema, dict) else None
            if name and isinstance(props, dict) and props:
                schemas[str(name)] = list(props.keys())
        return schemas

    def _absorb_text_tool_calls(self, response, model_id: str) -> bool:
        """Lift a written call into a real one.

        Native tool_calls already on the message win. The model's own channel
        (``<tool_call>``, ``[TOOL_REQUEST]``, Gemma 4 ``<|tool_call>call:``)
        is lifted before the text salvage. A call that exists only in reasoning
        is lifted without dumping the thought into the reply. One recovered
        call does not turn native tools off.
        """
        from Kerniq.models.text_tools import adopt_channel_calls, parse_text_tool_calls

        names = self._known_tool_names()
        schemas = self._known_tool_schemas()
        lifted = False
        for message in response.messages or []:
            content = message.content or ""
            if getattr(message, "tool_calls", None):
                cleaned, kept = adopt_channel_calls(content, message.tool_calls)
                message.content = cleaned
                message.tool_calls = kept
                continue
            cleaned, calls = adopt_channel_calls(content, None)
            source = "content"
            if not calls and names:
                cleaned, calls = parse_text_tool_calls(content, names, schemas)
            if not calls:
                meta = getattr(message, "metadata", None) or {}
                reasoning = str(meta.get("reasoning") or "") if isinstance(meta, dict) else ""
                if reasoning and not content.strip():
                    _ignored, calls = adopt_channel_calls(reasoning, None)
                    if not calls and names:
                        cleaned, calls = parse_text_tool_calls(reasoning, names, schemas)
                    source = "reasoning"
            if not calls:
                continue
            if source == "content":
                message.content = cleaned
            message.tool_calls = calls
            lifted = True
            logger.info(
                "Text tool call from %s (%s): %s",
                model_id or "model",
                source,
                [call.name for call in calls],
            )
        return lifted

    @staticmethod
    def _normalize_reply(text: str) -> str:
        import re
        s = (text or "").lower().strip()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"[`*_#>\-]+", "", s)
        return s[:2000]

    @staticmethod
    def _estimate_tokens(messages) -> int:
        total = 0
        for m in messages:
            total += len(m.content or "")
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    total += len(tc.name or "") + len(str(tc.arguments or ""))
        return max(1, total // 4)

    def _detect_content_loop(self, content: str, previous_assistant: list) -> bool:
        """True if content repeats a prior assistant reply or has heavy self-repetition."""
        import re
        norm = self._normalize_reply(content)
        if len(norm) < 40:
            return False
        # Compare against recent assistant texts
        for prev in previous_assistant[-6:]:
            pnorm = self._normalize_reply(prev)
            if not pnorm:
                continue
            if norm == pnorm:
                return True
            # high overlap: one contains the other (long)
            if len(norm) > 80 and len(pnorm) > 80:
                if norm in pnorm or pnorm in norm:
                    return True
                # token Jaccard on words
                a, b = set(norm.split()), set(pnorm.split())
                if a and b:
                    j = len(a & b) / max(1, len(a | b))
                    if j >= 0.92 and len(a) >= 12:
                        return True
        # Internal repetition: same long sentence twice
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", content) if len(s.strip()) > 30]
        seen = set()
        for s in sentences:
            key = self._normalize_reply(s)
            if key in seen:
                return True
            seen.add(key)
        # Stutter: same 12+ char chunk thrice
        for n in (20, 40, 60):
            if len(norm) < n * 3:
                continue
            counts = {}
            for i in range(0, len(norm) - n, max(1, n // 2)):
                chunk = norm[i : i + n]
                counts[chunk] = counts.get(chunk, 0) + 1
                if counts[chunk] >= 3:
                    return True
        return False

    def _continue_open_plan(self, context: TaskContext, continuations: int) -> bool:
        """An open TODO holds the run. A missing TODO holds it only when a plan was required."""
        raw = (context.metadata or {}).get("plan") or []
        if not isinstance(raw, list):
            raw = []
        open_items = [
            item for item in raw
            if isinstance(item, dict) and _plan_status_blocks(item.get("status"))
        ]
        if open_items:
            return True
        if not raw and self.compose_plan and not (context.metadata or {}).get("skip_plan_gate"):
            return continuations < 2
        return False

    def _should_close_open_plan(self, content: str, continuations: int) -> bool:
        """Close leftovers only when the model says it is done, or the budget is spent.

        One prose reply is not completion. "I will start the next item" used to
        fail the whole TODO because a single continuation counted as the end.
        """
        limit = max(1, int(getattr(self, "max_plan_continuations", 4) or 4))
        return self._declares_complete(content) or continuations >= limit

    def _declares_complete(self, content: str) -> bool:
        """The model closed the task. Leftover TODO items are then recorded as failed."""
        text = content or ""
        if "TASK_COMPLETED" in text:
            return True
        low = text.lower()
        markers = (
            "work is complete",
            "work is completed",
            "task is complete",
            "task is completed",
            "i have finished",
            "i'm finished",
            "i am finished",
            "работа завершена",
            "работа выполнена",
            "задача выполнена",
            "задача завершена",
        )
        return any(marker in low for marker in markers)

    async def _fail_open_items(self, context: TaskContext) -> int:
        """Platform close-out. Not an update_plan call, so later items are not reopened."""
        raw = (context.metadata or {}).get("plan") or []
        if not isinstance(raw, list):
            return 0
        items = []
        changed = 0
        for item in raw:
            if not isinstance(item, dict):
                continue
            copy = {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("text") or ""),
                "status": str(item.get("status") or "pending"),
            }
            if copy["title"] and _plan_status_blocks(copy["status"]):
                copy["status"] = "failed"
                changed += 1
            items.append(copy)
        if not changed:
            return 0
        context.metadata["plan"] = items
        archive = [
            dict(item) for item in ((context.metadata or {}).get("plan_archive") or [])
            if isinstance(item, dict)
        ]
        seen = {str(item.get("id") or "") for item in archive}
        for item in items:
            if item["status"] != "failed" or not item["id"] or item["id"] in seen:
                continue
            archive.append(dict(item))
            seen.add(item["id"])
        context.metadata["plan_archive"] = archive
        cb = getattr(self, "on_plan", None)
        if callable(cb):
            try:
                cb(items, archive)
            except Exception:
                logger.exception("on_plan failed")
        self._pin_todo(context)
        return changed

    def _todo_note(self, context: TaskContext) -> str:
        raw = (context.metadata or {}).get("plan") or []
        archive = (context.metadata or {}).get("plan_archive") or []
        if not isinstance(raw, list):
            raw = []
        if not isinstance(archive, list):
            archive = []
        open_lines = []
        failed_lines = []
        done_ids = set()
        done_lines = []
        for item in archive:
            if not isinstance(item, dict):
                continue
            done_ids.add(str(item.get("id") or ""))
            title = str(item.get("title") or "").strip()
            if title:
                done_lines.append(f"- {title}")
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            status = str(item.get("status") or "pending")
            if status == "failed":
                if title:
                    failed_lines.append(f"- {title}")
                continue
            if status in ("done", "skipped"):
                if str(item.get("id") or "") not in done_ids and title:
                    done_lines.append(f"- [{status}] {title}")
                continue
            if title:
                open_lines.append(f"- [{status}] {title}")
        if not open_lines and not done_lines and not failed_lines:
            return ""
        return (
            "[Pinned TODO. This survives compaction. Archived items are already done. "
            "Do not redo them and do not put them back on the live list.]\n"
            "Open (pending, active, and frozen block the end):\n"
            + ("\n".join(open_lines) or "- (none)")
            + "\nFailed (recorded, do not repeat the same attempt, does not block the end):\n"
            + ("\n".join(failed_lines) or "- (none)")
            + "\nDone items stay on the list. Do not delete them and do not redo them:\n"
            + ("\n".join(done_lines) or "- (none)")
            + "\n[/Pinned TODO]"
        )

    def _strip_pinned_todo(self, text: str) -> str:
        mark = "[Pinned TODO."
        end = "[/Pinned TODO]"
        raw = text or ""
        while raw.startswith(mark):
            at = raw.find(end)
            if at < 0:
                break
            raw = raw[at + len(end):].lstrip("\n")
        return raw

    def _pin_todo(self, context: TaskContext) -> None:
        """Refresh the leading TODO without dropping the system prompt.

        The pin is prepended to the first system message. The next turn that
        message starts with the pin, so it must be stripped and kept. Dropping
        every message that starts with the pin throws away the prompt.
        """
        note = self._todo_note(context)
        mark = "[Pinned TODO."
        kept = []
        for message in context.messages:
            if message.role == MessageRole.SYSTEM and mark in (message.content or ""):
                body = self._strip_pinned_todo(message.content or "").strip()
                if not body:
                    continue
                message.content = body
            kept.append(message)
        if not note:
            context.messages = kept
            self._pin_tool_gate(context)
            return
        if kept and kept[0].role == MessageRole.SYSTEM:
            body = self._strip_pinned_todo(kept[0].content or "").strip()
            kept[0].content = note + "\n\n" + body if body else note
        else:
            kept.insert(0, Message(role=MessageRole.SYSTEM, content=note))
        context.messages = kept
        self._pin_tool_gate(context)

    def _offered_tool_names(self, context: TaskContext) -> set:
        names = set()
        for spec in self._tools_for_mode(context):
            name = _spec_name(spec)
            if name:
                names.add(name)
        return names

    def _pin_tool_gate(self, context: TaskContext) -> None:
        """Do not paste a second tool list into the system text.

        The tools array is the list. LM Studio copies it into the chat template
        and that template owns the call syntax. A handwritten catalog next to it
        makes the model mix formats. The only extra line is the first-turn rule
        that update_plan is the only call until a TODO exists.
        """
        import re

        names = []
        for spec in self._tools_for_mode(context):
            name = _spec_name(spec)
            if name and name not in names:
                names.append(name)
        gate_first = (
            self.compose_plan
            and not (context.metadata or {}).get("skip_plan_gate")
            and self._todo_missing(context)
            and names == ["update_plan"]
        )
        line = ""
        if gate_first:
            line = (
                "Until a TODO exists, call update_plan through the tool interface "
                "and no other tool."
            )
        note = str((context.metadata or {}).get("kerniq_note") or "").strip()
        gate = re.compile(
            r"\n*(?:\[Tools this turn:.*?\]"
            r"|Until a TODO exists, call update_plan through the tool interface and no other tool\.)",
            re.S,
        )
        note_re = re.compile(r"\n*\[Kerniq note\].*?\[/Kerniq note\]", re.S)
        for message in context.messages:
            if message.role == MessageRole.SYSTEM:
                message.content = note_re.sub("", gate.sub("", message.content or "")).strip()
        extra = line
        if note:
            extra = ((extra + "\n\n") if extra else "") + "[Kerniq note]\n" + note + "\n[/Kerniq note]"
        if not extra:
            return
        if context.messages and context.messages[0].role == MessageRole.SYSTEM:
            body = (context.messages[0].content or "").strip()
            context.messages[0].content = (body + "\n\n" + extra) if body else extra
        else:
            context.messages.insert(0, Message(role=MessageRole.SYSTEM, content=extra))

    def _stop_requested(self, context: TaskContext) -> bool:
        if getattr(context, "cancelled", False):
            return True
        check = getattr(self, "cancel_check", None)
        if not callable(check):
            return False
        try:
            if check():
                context.cancelled = True
                return True
        except Exception:
            logger.exception("Cancel check failed")
        return False

    async def _await_or_stop(self, coro, context: TaskContext):
        """Run `coro` until it finishes or the user hits Stop.

        Cancel is checked several times a second, not only between iterations,
        so a blocked model call or tool does not ignore Stop. If the call
        swallows cancellation (a stuck socket), the run still ends: the UI
        must not sit on "Stopping…" until the provider timeout.
        """
        task = asyncio.create_task(coro)
        try:
            while not task.done():
                if self._stop_requested(context):
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, 1.5)
                    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                        pass
                    if not task.done():
                        logger.warning("Stop: in-flight call did not exit within 1.5s; abandoning it")
                    raise _RunStopped()
                await asyncio.sleep(0.2)
            return task.result()
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(task, 1.5)
            raise

    _TRUNC_MARK = "[Context truncated to fit the model window."
    _EMPTY_NUDGE = (
        "Your last reply was empty. Answer, or call a tool through the tool interface. "
        "Do not print the call as text."
    )

    def _strip_truncation_notices(self, messages):
        """Remove prior auto-inserted truncation / empty-nudge system notes."""
        out = []
        for m in messages:
            c = (m.content or "")
            if m.role == MessageRole.SYSTEM and (
                c.startswith(self._TRUNC_MARK) or c.startswith("Your last reply was empty")
            ):
                continue
            out.append(m)
        return out

    @staticmethod
    def _message_groups(messages):
        """Split history into groups.

        A group is one user or assistant message, plus the tool results that follow it.
        Orphan tool messages are dropped later by sanitize.
        """
        groups = []
        i = 0
        n = len(messages)
        while i < n:
            m = messages[i]
            if m.role == MessageRole.USER:
                groups.append([m])
                i += 1
            elif m.role == MessageRole.ASSISTANT:
                g = [m]
                i += 1
                # attach following tool results for this assistant's tool_calls
                while i < n and messages[i].role == MessageRole.TOOL:
                    g.append(messages[i])
                    i += 1
                groups.append(g)
            elif m.role == MessageRole.TOOL:
                # orphan tool — keep as own group; sanitize will drop if broken
                groups.append([m])
                i += 1
            else:
                groups.append([m])
                i += 1
        return groups

    def _trim_messages_to_budget(self, messages, budget_tokens: int):
        """Keep primary system, the original goal, and newest complete groups."""
        messages = self._strip_truncation_notices(list(messages))
        if budget_tokens <= 0:
            return messages
        if self._estimate_tokens(messages) <= budget_tokens:
            return messages

        systems = [m for m in messages if m.role == MessageRole.SYSTEM]
        kept_systems = []
        for m in systems:
            text = m.content or ""
            if not kept_systems or text.startswith("[Compacted context.") or text.startswith("[Pinned TODO."):
                kept_systems.append(m)
        rest = [m for m in messages if m.role != MessageRole.SYSTEM]
        groups = self._message_groups(rest)

        pinned = []
        if groups and groups[0] and groups[0][0].role == MessageRole.USER:
            pinned = groups[0]
            groups = groups[1:]

        kept_rev = []
        used = self._estimate_tokens(kept_systems) + self._estimate_tokens(pinned)
        for g in reversed(groups):
            cost = self._estimate_tokens(g)
            if used + cost > budget_tokens and kept_rev:
                break
            kept_rev.append(g)
            used += cost

        kept = []
        for g in reversed(kept_rev):
            kept.extend(g)

        # Hard-truncate oversized tool payloads inside kept groups
        for m in kept:
            if m.role == MessageRole.TOOL and m.content and len(m.content) > 12000:
                m.content = m.content[:12000] + "\n…[tool output truncated]"

        kept = kept_systems + pinned + kept
        trimmed = len(kept) < len(messages)
        if trimmed:
            note = (
                "[Context trimmed. The compaction plugin is off or did not run, "
                "so older turns were dropped. The TODO and the latest turns were kept.]"
            )
            if not any((m.content or "").startswith("[Context trimmed.") for m in kept):
                kept = [Message(role=MessageRole.SYSTEM, content=note)] + kept
            self._notify(
                "trimmed",
                "Context trimmed. Older turns were dropped. The latest turns were kept.",
            )
        return kept

    @staticmethod
    def _is_context_overflow(exc: BaseException) -> bool:
        from Kerniq.core.runtime_flow import is_context_overflow
        return is_context_overflow(exc)

    def _sanitize_for_provider(self, messages):
        """Make history valid for strict chat templates (Mistral/Gemma/etc.).

        Rules enforced:
        - at most leading system messages
        - drop orphan tool messages (no preceding assistant tool_calls)
        - drop empty assistant messages without tool_calls
        - drop mid-conversation system nudges (re-inject as user if needed)
        - ensure tool results only follow assistant with tool_calls
        """
        messages = self._strip_truncation_notices(list(messages))
        systems = []
        body = []
        for m in messages:
            if m.role == MessageRole.SYSTEM:
                # keep only the first real system prompt(s) at the front
                if not body:
                    systems.append(m)
                # skip mid-stream system messages (empty nudges, trunc notes already stripped)
                continue
            body.append(m)

        out = list(systems)
        pending_tool_ids = set()
        last_role = None

        for m in body:
            if m.role == MessageRole.TOOL:
                tid = m.tool_call_id or ""
                if tid and tid in pending_tool_ids:
                    out.append(m)
                    pending_tool_ids.discard(tid)
                    last_role = "tool"
                elif not pending_tool_ids and last_role == "assistant":
                    # some providers omit ids — allow tool right after assistant with tool_calls
                    out.append(m)
                    last_role = "tool"
                else:
                    logger.warning("Dropping orphan tool message id=%s name=%s", tid, m.name)
                continue

            if m.role == MessageRole.ASSISTANT:
                has_tools = bool(getattr(m, "tool_calls", None))
                content = (m.content or "").strip()
                if not content and not has_tools:
                    logger.warning("Dropping empty assistant message")
                    continue
                out.append(m)
                pending_tool_ids = set()
                if has_tools:
                    for tc in m.tool_calls or []:
                        if tc.id:
                            pending_tool_ids.add(tc.id)
                last_role = "assistant"
                continue

            if m.role == MessageRole.USER:
                out.append(m)
                pending_tool_ids = set()
                last_role = "user"
                continue

            # ignore unknown

        # If we still have unresolved tool_calls at the end, that's ok — model will continue
        return out

    def _nudge_after_empty(self, context: TaskContext) -> None:
        """Ask the model to continue. This stays in the system note, not the user chat."""
        context.metadata["kerniq_note"] = self._EMPTY_NUDGE

    def _needs_plan_draft(self, context: TaskContext) -> bool:
        """Plan may not hand off until the research itself is in the transcript."""
        if str((context.metadata or {}).get("agent_mode") or "") != "plan":
            return False
        if not (context.metadata or {}).get("plan_handoff"):
            return False
        for message in context.messages:
            text = message.content or ""
            if "===ACT_DRAFT===" in text and "===END_DRAFT===" in text:
                return False
        return True

    def _notify(self, kind: str, text: str) -> None:
        cb = getattr(self, "on_notice", None)
        if not callable(cb):
            return
        try:
            cb(kind, text)
        except Exception:
            logger.exception("Notice callback failed")

    def _user_note(self, context: TaskContext, text: str) -> None:
        """Feedback the model must see. It is not a user message and is not saved as one."""
        context.metadata["kerniq_note"] = text

    def _checkpoint(self, context: TaskContext) -> None:
        cb = getattr(self, "on_progress", None)
        if not cb:
            return
        try:
            cb(context)
        except Exception:
            logger.exception("Progress checkpoint failed")

    def _finish(self, context: TaskContext, content: str, outcome: str, detail: str = "") -> str:
        context.metadata["outcome"] = outcome
        if detail:
            context.metadata["outcome_detail"] = detail
        self._checkpoint(context)
        text = content or ""
        if outcome not in ("verified", "cancelled"):
            note = f"[kerniq] outcome={outcome}"
            if detail:
                note += f" — {detail}"
            if note not in text:
                text = (text.rstrip() + "\n\n" + note).strip()
        return text

    def _todo_missing(self, context: TaskContext) -> bool:
        raw = (context.metadata or {}).get("plan") or []
        if not isinstance(raw, list):
            return True
        return not any(
            isinstance(item, dict) and str(item.get("title") or item.get("text") or "").strip()
            for item in raw
        )

    def _tools_for_mode(self, context: TaskContext):
        specs = []
        registry = self.tool_registry
        if registry is not None and hasattr(registry, "get_tools_for_model"):
            specs = list(registry.get_tools_for_model() or [])
        mode = str((context.metadata or {}).get("agent_mode") or "act")
        skip_gate = bool((context.metadata or {}).get("skip_plan_gate"))
        # "Build a plan" limits the first turn of a run to update_plan.
        # Act after a plan handoff is not that first turn: it gets every enabled tool.
        if self.compose_plan and not skip_gate and self._todo_missing(context):
            only = [spec for spec in specs if _spec_name(spec) == "update_plan"]
            if only:
                return only
        if mode != "plan":
            specs = list(specs)
        else:
            allowed = {
                tool.name
                for tool in self.tool_registry.list_tools()
                if self.tool_included_in_plan(tool)
            }
            specs = [spec for spec in specs if _spec_name(spec) in allowed]
        if not (context.metadata or {}).get("vision"):
            specs = [spec for spec in specs if _spec_name(spec) != "view_image"]
        return specs

    async def _exhaust_current_item(self, context: TaskContext) -> str:
        """The same lookup failed often enough. Record it and move on."""
        raw = (context.metadata or {}).get("plan") or []
        if not isinstance(raw, list):
            return ""
        items = []
        title = ""
        marked = False
        for item in raw:
            if not isinstance(item, dict):
                continue
            copy = {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or item.get("text") or ""),
                "status": str(item.get("status") or "pending"),
            }
            if not marked and copy["status"] == "active" and copy["title"]:
                copy["status"] = "failed"
                title = copy["title"]
                marked = True
            items.append(copy)
        if not marked:
            return ""
        try:
            from Kerniq.tools.packs.plan.tools import UpdatePlanTool

            await UpdatePlanTool().execute({"items": items}, context)
        except Exception:
            logger.exception("Could not mark the current TODO item failed")
            return ""
        plan = (context.metadata or {}).get("plan") or []
        archive = (context.metadata or {}).get("plan_archive") or []
        cb = getattr(self, "on_plan", None)
        if callable(cb):
            try:
                cb(plan, archive)
            except Exception:
                logger.exception("on_plan failed")
        self._pin_todo(context)
        return title

    @staticmethod
    def tool_included_in_plan(tool) -> bool:
        """Plan mode offers a tool only when that tool include_in_plan flag is on.

        update_plan is not special. If it is disabled or opted out of Plan,
        Build a plan cannot be turned on.
        """
        if tool is None:
            return False
        if getattr(tool, "agent_visible", True) is False:
            return False
        return bool(getattr(tool, "include_in_plan", False))

    @staticmethod
    def plan_blocks_tool(context: TaskContext, tool) -> bool:
        if str((context.metadata or {}).get("agent_mode") or "act") != "plan":
            return False
        if tool is None:
            return False
        return not Orchestrator.tool_included_in_plan(tool)

    async def _maybe_compact(self, context: TaskContext) -> None:
        compactor = getattr(self, "compactor", None)
        if compactor is None or not getattr(compactor, "cfg_enabled", True):
            return
        needs = getattr(compactor, "needs_compact", None)
        compact = getattr(compactor, "compact", None)
        if not callable(needs) or not callable(compact):
            return
        try:
            if not needs(context.messages):
                return
            summary = context.metadata.get("context_summary")
            summarize = getattr(compactor, "summarize", None)
            if callable(summarize):
                try:
                    produced = await summarize(context.messages, self.provider)
                    if produced:
                        summary = produced
                except Exception:
                    logger.exception("Model compact failed; using extractive outline")
            before_compact = len(context.messages)
            context.messages = compact(context.messages, summary)
            stored = getattr(compactor, "last_summary", None)
            if stored:
                context.metadata["context_summary"] = stored
            context.metadata["compacted"] = True
            self._pin_todo(context)
            if len(context.messages) < before_compact:
                self._notify(
                    "compacted",
                    "Context compacted. Older turns were replaced by a memory note.",
                )
            self._checkpoint(context)
        except Exception:
            logger.exception("Context compactor failed; keeping full history")


    def _transient_provider_error(self, exc: Exception) -> bool:
        if isinstance(exc, ProviderError) and exc.code in (
            ErrorCode.PROVIDER_UNAVAILABLE,
            ErrorCode.PROVIDER_REQUEST_FAILED,
        ):
            text = str(exc).lower()
            if (
                "not loaded" in text
                or "no model" in text
                or "no loaded" in text
                or "expected modelresponse" in text
            ):
                return False
            return True
        text = str(exc).lower()
        return "timeout" in text or "connect" in text or "temporarily" in text

    async def _generate_with_retries(self, request: ModelRequest) -> ModelResponse:
        attempt = 0
        while True:
            try:
                response = await self.provider.generate(request)
            except Exception as exc:
                from ..models.cancel import StreamCancelled, cancelled_response

                if isinstance(exc, StreamCancelled):
                    return cancelled_response()
                if not self._transient_provider_error(exc) or attempt >= self.provider_retries:
                    raise
                attempt += 1
                logger.warning("Provider error, retry %s/%s: %s", attempt, self.provider_retries, exc)
                continue
            if not isinstance(response, ModelResponse):
                raise ProviderError(
                    ErrorCode.PROVIDER_REQUEST_FAILED,
                    f"Provider returned {type(response).__name__}, expected ModelResponse",
                )
            return response

    async def run(self, context: TaskContext) -> str:
        iteration = 0
        last_tool_sig: Optional[str] = None
        tool_streak = 0
        loop_nudged = False
        empty_retries = 0
        content_loop_hits = 0
        plan_continuations = 0
        plan_draft_nudges = 0
        verify_failures = 0
        assistant_history: list = []
        ctx_limit = int(getattr(self, "context_limit", 0) or 0) or int(
            (context.metadata or {}).get("context_limit") or 0
        )
        context.metadata["context_limit_estimate"] = ctx_limit
        if ctx_limit > 0:
            input_budget = max(4096, int(ctx_limit * 0.85))
        else:
            input_budget = 10**9
        mode_name = str((context.metadata or {}).get("agent_mode") or "act")
        context.metadata["iterations_used"] = 0
        if "vision" not in (context.metadata or {}):
            try:
                from ..models.vision import provider_sees_images

                context.metadata["vision"] = bool(await provider_sees_images(self.provider))
            except Exception:
                logger.exception("vision probe failed")
                context.metadata["vision"] = False
        logger.info(
            "Iteration budget reset for %s mode (limit %s). Context compaction is not counted.",
            mode_name,
            self.max_iterations,
        )

        while iteration < self.max_iterations:
            if getattr(context, "cancelled", False) or self._stop_requested(context):
                logger.info("Orchestration cancelled")
                return self._finish(context, "Stopped by user.", "cancelled", "Stopped by user.")
            # Compaction may call the model, but it is bookkeeping and must not spend an iteration.
            await self._maybe_compact(context)
            iteration += 1
            context.metadata["iterations_used"] = iteration
            logger.info(f"Orchestration iteration {iteration}/{self.max_iterations}")
            context.messages = self._strip_truncation_notices(context.messages)
            est = self._estimate_tokens(context.messages)
            if est > input_budget:
                before = len(context.messages)
                context.messages = self._trim_messages_to_budget(context.messages, input_budget)
                logger.warning(
                    "Context overflow: %s msgs -> %s (est=%s budget=%s)",
                    before, len(context.messages), est, input_budget,
                )
            self._pin_todo(context)
            context.metadata.pop("kerniq_note", None)
            safe_messages = self._sanitize_for_provider(context.messages)
            if not any(m.role == MessageRole.USER for m in safe_messages):
                safe_messages = list(safe_messages) + [
                    Message(role=MessageRole.USER, content=context.goal or "Continue the task.")
                ]
                logger.warning("No user message after sanitize; re-added goal")
            if len(safe_messages) != len(context.messages):
                logger.info(
                    "Sanitized messages %s -> %s roles=%s",
                    len(context.messages),
                    len(safe_messages),
                    [m.role.value for m in safe_messages],
                )
                context.messages = list(safe_messages)

            options = self.generation_options
            if context.metadata.get("unlimited_final"):
                options = self.generation_options.model_copy(update={"max_tokens": None})
                context.metadata["unlimited_final"] = False
                logger.info("Final answer is not capped. The model may use the provider output limit.")

            model_id = str(getattr(self.provider, "model", "") or "").strip()
            request_messages = safe_messages
            request_tools = self._tools_for_mode(context)
            request = ModelRequest(
                messages=request_messages,
                session_id=context.session_id,
                tools=request_tools,
                options=options,
            )

            try:
                response = await self._await_or_stop(self._generate_with_retries(request), context)
            except _RunStopped:
                logger.info("Stop requested during model generation")
                return self._finish(context, "Stopped by user.", "cancelled", "Stopped by user.")
            except Exception as exc:
                if int(context.metadata.get("overflow_retries") or 0) < 1 and self._is_context_overflow(exc):
                    context.metadata["overflow_retries"] = 1
                    before = len(context.messages)
                    tighter = max(2048, input_budget // 2)
                    context.messages = self._trim_messages_to_budget(context.messages, tighter)
                    self._pin_todo(context)
                    logger.warning(
                        "Provider rejected the prompt as too long (%s messages -> %s). Trimmed and retrying once.",
                        before,
                        len(context.messages),
                    )
                    iteration -= 1
                    continue
                logger.exception("Provider failed")
                return self._finish(
                    context,
                    f"Stopped: model provider failed: {exc}",
                    "provider_error",
                    str(exc),
                )

            if (
                getattr(response, "finish_reason", None) == "cancelled"
                or (response.metadata or {}).get("cancelled")
            ):
                context.cancelled = True
                partial = []
                for msg in response.messages or []:
                    text = (msg.content or "").strip()
                    if text or msg.tool_calls:
                        context.add_message(msg)
                    if text:
                        partial.append(msg.content)
                return self._finish(
                    context,
                    "\n".join(partial).strip() or "Stopped by user.",
                    "cancelled",
                    "Stopped by user.",
                )

            if not response.messages:
                empty_retries += 1
                if empty_retries <= self.max_empty_retries:
                    self._nudge_after_empty(context)
                    continue
                return self._finish(
                    context,
                    "Stopped: model returned an empty or unusable response.",
                    "empty_response",
                    "No assistant message.",
                )

            from .runtime_flow import promote_reasoning

            promote_reasoning(response)
            if self._absorb_text_tool_calls(response, model_id):
                # Keep native tools. A recovered call is this turn only.
                pass

            finish = str(getattr(response, "finish_reason", "") or "")
            pending_calls = []
            for msg in response.messages:
                if msg.tool_calls:
                    pending_calls.extend(msg.tool_calls)
            if (
                not pending_calls
                and finish in ("length", "max_tokens")
                and not context.metadata.get("final_output_expanded")
            ):
                context.metadata["final_output_expanded"] = True
                context.metadata["unlimited_final"] = True
                logger.info("The last reply was cut by the output cap. Retrying with no cap.")
                iteration -= 1
                continue

            content_nudged = False
            for msg in response.messages:
                text = (msg.content or "").strip()
                if text and self._detect_content_loop(text, assistant_history):
                    content_loop_hits += 1
                    logger.warning("Content loop detected (hit=%s)", content_loop_hits)
                    if content_loop_hits >= self.max_content_loop_hits:
                        return self._finish(
                            context,
                            "Stopped: the model started repeating the same reasoning/answer "
                            "(loop protection).",
                            "content_loop",
                            "Repeated assistant text.",
                        )
                    self._user_note(
                        context,
                        "You are repeating previous content. Do not restate the same "
                        "reasoning. Either call a different tool or give a final concise answer.",
                    )
                    content_nudged = True
                if text:
                    assistant_history.append(text)

            for msg in response.messages:
                if msg.role == MessageRole.ASSISTANT and not (msg.content or "").strip() and not msg.tool_calls:
                    continue
                context.add_message(msg)

            tool_calls = []
            for msg in response.messages:
                if msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)

            if not tool_calls:
                if content_nudged:
                    continue
                final_msg = response.messages[-1]
                content = (final_msg.content if final_msg else "") or ""
                while context.messages and context.messages[-1].role == MessageRole.ASSISTANT:
                    last = context.messages[-1]
                    if (last.content or "").strip() or last.tool_calls:
                        break
                    context.messages.pop()
                if not content.strip():
                    empty_retries += 1
                    if empty_retries <= self.max_empty_retries:
                        self._nudge_after_empty(context)
                        continue
                    return self._finish(
                        context,
                        "Stopped: model returned empty responses repeatedly.",
                        "empty_response",
                        "Empty assistant content.",
                    )
                empty_retries = 0
                skip_gate = bool((context.metadata or {}).get("skip_plan_gate"))
                declared = self._declares_complete(content)
                open_now = [
                    item for item in ((context.metadata or {}).get("plan") or [])
                    if isinstance(item, dict) and _plan_status_blocks(item.get("status"))
                ]
                # TASK_COMPLETED is the end of the turn. Do not send another
                # prompt, including the "write a TODO" nudge, and do not send
                # the model its own reply back. An open TODO is closed here.
                if declared:
                    if open_now:
                        await self._fail_open_items(context)
                elif self.compose_plan and not skip_gate and self._todo_missing(context):
                    if plan_continuations < 3:
                        plan_continuations += 1
                        self._user_note(
                            context,
                            "There is no TODO. Your next call must be update_plan and nothing else. "
                            "Do not answer, and do not explore the project, until that list exists.",
                        )
                        continue
                    return self._finish(
                        context,
                        "Stopped: the model answered without writing a TODO. update_plan has to run first.",
                        "no_plan",
                        "No TODO was published.",
                    )
                elif open_now and self._should_close_open_plan(content, plan_continuations):
                    await self._fail_open_items(context)
                elif self._continue_open_plan(context, plan_continuations):
                    plan_continuations += 1
                    mode = str((context.metadata or {}).get("agent_mode") or "act")
                    if mode == "plan" and not (context.metadata or {}).get("plan"):
                        note = (
                            "Plan mode is not done. The first call is update_plan if a TODO is required. "
                            "Then keep researching. Do not implement."
                        )
                    elif open_now:
                        note = (
                            "The TODO is still open. Work strictly in order. "
                            "Only the first unfinished item is current, and you may change only that one. "
                            "Mark it done if you finished it. "
                            "If the same attempt is empty about three times, or you have given up, mark that one item failed. "
                            "failed does not block the end. frozen does. "
                            "If the work is actually finished, say so and end with TASK_COMPLETED. "
                            "Unfinished items will be recorded as failed."
                        )
                    else:
                        note = (
                            "Write a short TODO with update_plan before you finish. "
                            "You cannot end this task without one."
                        )
                    self._user_note(context, note)
                    continue
                if (
                    self._needs_plan_draft(context)
                    and plan_draft_nudges < 2
                    and not (declared and self._todo_missing(context))
                ):
                    plan_draft_nudges += 1
                    self._user_note(
                        context,
                        "The research list is closed, but Act cannot see this chat. "
                        "Your next message must be the audit, with no tool calls. "
                        "Repeat what you already learned inside this block, even if you wrote it earlier:\n"
                        "===ACT_DRAFT===\n"
                        "project:\ntask:\nfindings:\nreasoning:\nfiles:\nrisks:\nsuggested_steps:\n"
                        "===END_DRAFT===",
                    )
                    continue
                if self.verifier:
                    verification = await self.verifier.verify(context.goal, context, context.workspace)
                    context.metadata["verification"] = verification.model_dump()
                    if not verification.passed:
                        verify_failures += 1
                        logger.info("Verification failed: %s", verification.message)
                        if verify_failures > self.max_verification_retries:
                            return self._finish(
                                context,
                                content,
                                "verification_failed",
                                verification.message,
                            )
                        self._user_note(
                            context,
                            "Verification failed: "
                            + verification.message
                            + ". Correct the workspace so the original goal is met. "
                            "Do not replace the goal with a simpler one.",
                        )
                        continue
                    if is_unverified(verification):
                        return self._finish(context, content, "unverified", verification.message)
                    return self._finish(context, content, "verified", verification.message)
                return self._finish(
                    context,
                    content,
                    "unverified",
                    "No verifier was configured.",
                )

            try:
                sig = "|".join(
                    f"{c.name}:{json.dumps(c.arguments or {}, sort_keys=True, ensure_ascii=False)}"
                    for c in tool_calls
                )
            except Exception:
                sig = "|".join(c.name for c in tool_calls)
            if sig and sig == last_tool_sig:
                tool_streak += 1
            else:
                tool_streak = 1
                last_tool_sig = sig
            if tool_streak >= self.max_identical_tool_streak:
                if not loop_nudged:
                    loop_nudged = True
                    tool_streak = 0
                    last_tool_sig = None
                    logger.warning("Identical tool streak — asking for a different approach")
                    for call in tool_calls:
                        context.add_message(Message(
                            role=MessageRole.TOOL,
                            content=(
                                "Skipped: this exact tool call was already repeated without "
                                "a change in arguments. Do not call it again. "
                                "State the blocker or use different arguments."
                            ),
                            tool_call_id=call.id,
                            name=call.name,
                        ))
                    failed_title = await self._exhaust_current_item(context)
                    if failed_title:
                        note = (
                            "The same tool call was repeated and did not change the outcome. "
                            f"The current TODO item was marked failed: {failed_title}. "
                            "failed stays on the list and does not block the end. Do not repeat that lookup. "
                            "The next item is now current. Continue with it, or stop if none remain."
                        )
                    else:
                        note = (
                            "The same tool call was repeated and did not change the outcome. "
                            "Do not call it again. If this was the current TODO item and the attempt is exhausted, "
                            "mark that item failed with update_plan. failed does not block the end. "
                            "Mark an item done only when you actually found or finished it."
                        )
                    self._user_note(context, note)
                    continue
                logger.warning("Identical tool streak=%s sig=%s — stopping loop", tool_streak, sig[:200])
                return self._finish(
                    context,
                    "Stopped: the model repeated the same tool call(s) "
                    f"{tool_streak} times in a row (loop protection).",
                    "tool_loop",
                    sig[:300],
                )

            skip_gate = bool((context.metadata or {}).get("skip_plan_gate"))
            todo_missing = self.compose_plan and not skip_gate and self._todo_missing(context)
            offered = self._offered_tool_names(context)
            for call in tool_calls:
                if self._stop_requested(context):
                    logger.info("Stop requested before the next tool")
                    return self._finish(context, "Stopped by user.", "cancelled", "Stopped by user.")
                logger.info(f"Executing tool: {call.name} with args {call.arguments}")
                tool = self.tool_registry.get_tool(call.name)
                schema = tool.input_schema if tool is not None else None
                invalid = argument_error(schema, call.arguments or {})
                if tool is not None and hasattr(tool, "validate_arguments"):
                    try:
                        if tool.validate_arguments(call.arguments or {}) is False and not invalid:
                            invalid = "arguments rejected by the tool"
                    except Exception as exc:
                        invalid = str(exc)
                if invalid:
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=json.dumps(
                            {"success": False, "stop_reason": "invalid_args", "error": invalid},
                            ensure_ascii=False,
                        ),
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                import json as _json
                denied_sig = call.name + "\n" + _json.dumps(call.arguments or {}, sort_keys=True, ensure_ascii=False)
                if denied_sig in set((context.metadata or {}).get("user_denied") or []):
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=(
                            "USER_DENIED: The user already refused this exact call. "
                            f"Tool `{call.name}` was not run again. "
                            "Do not retry it. Choose a different approach."
                        ),
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                if offered is not None and call.name not in offered:
                    if todo_missing:
                        refusal = (
                            "No TODO yet. The first call must be update_plan with the full list. "
                            "Do not explore the project until that list exists. "
                            f"{call.name} was not run."
                        )
                    else:
                        refusal = (
                            f"{call.name} is not available on this turn and was not run. "
                            "Call only a tool that was offered through the tool interface."
                        )
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=refusal,
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                if tool is not None and self.plan_blocks_tool(context, tool):
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=(
                            "Plan mode does not include this tool. "
                            f"{call.name} was not run."
                        ),
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                if self.security_policy:
                    declared = getattr(tool, "risk_level", "medium") if tool else "medium"
                    decision = self.security_policy.evaluate_tool_call(
                        call.name, call.arguments or {}, declared, tool=tool
                    )
                    if decision == PolicyDecision.DENY:
                        error_msg = f"Security Error: Execution of tool {call.name} is denied by policy."
                        if call.name in ("run_command", "terminal"):
                            reason = self.security_policy.terminal_block_reason(
                                str((call.arguments or {}).get("command", ""))
                            )
                            if reason:
                                error_msg = f"Security Error: {reason}"
                        context.add_message(Message(
                            role=MessageRole.TOOL,
                            content=error_msg,
                            tool_call_id=call.id,
                            name=call.name,
                        ))
                        continue
                    elif decision == PolicyDecision.REQUIRE_APPROVAL:
                        risk_name = self.security_policy.resolve_risk(call.name, declared, tool).value
                        if self.approval_provider:
                            from ..interfaces.approvals import ApprovalRequest
                            import uuid
                            from datetime import datetime, timezone

                            consequences = (
                                "This runs with the OS permissions of the Kerniq process. "
                                "The shell is not an OS sandbox. Absolute paths and encoded "
                                "commands are still rejected, but a general interpreter can "
                                "still touch files the OS user can access."
                                if call.name in ("run_command", "terminal")
                                else "This action can change or remove workspace data."
                            )
                            app_req = ApprovalRequest(
                                request_id=uuid.uuid4(),
                                tool_id=call.name,
                                arguments=call.arguments or {},
                                risk_level=risk_name,
                                description=f"Executing {call.name}",
                                timestamp=datetime.now(timezone.utc).isoformat(),
                                consequences=consequences,
                            )
                            app_res = await self.approval_provider.request_approval(app_req)
                            if app_res.decision != "allow":
                                import json as _json
                                sig = call.name + "\n" + _json.dumps(call.arguments or {}, sort_keys=True, ensure_ascii=False)
                                denied = list((context.metadata or {}).get("user_denied") or [])
                                if sig not in denied:
                                    denied.append(sig)
                                context.metadata["user_denied"] = denied
                                shown = _json.dumps(call.arguments or {}, ensure_ascii=False)
                                error_msg = (
                                    "USER_DENIED: The user refused this call. "
                                    f"Tool `{call.name}` with arguments {shown} was not executed. "
                                    "This is not a tool error and not a transient failure. "
                                    "Do not call this tool again with the same arguments. "
                                    "Pick a different approach or ask the user."
                                )
                                context.add_message(Message(
                                    role=MessageRole.TOOL,
                                    content=error_msg,
                                    tool_call_id=call.id,
                                    name=call.name,
                                ))
                                continue
                        else:
                            error_msg = (
                                f"Security Error: Tool {call.name} requires manual approval "
                                "but no provider is configured."
                            )
                            context.add_message(Message(
                                role=MessageRole.TOOL,
                                content=error_msg,
                                tool_call_id=call.id,
                                name=call.name,
                            ))
                            continue

                if not tool:
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=f"Tool {call.name} not found",
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                try:
                    with use_task(context):
                        result = await self._await_or_stop(
                            tool.execute(call.arguments, context), context
                        )
                except _RunStopped:
                    logger.info("Stop requested during tool %s", call.name)
                    return self._finish(context, "Stopped by user.", "cancelled", "Stopped by user.")
                except Exception as exc:
                    logger.exception("Tool %s raised", call.name)
                    text = str(exc)
                    low = text.lower()
                    if "timed out" in low or "timeout" in low:
                        note = "External error: the tool timed out. " + text
                    elif isinstance(exc, FileNotFoundError):
                        note = "File not found. " + text
                    elif isinstance(exc, PermissionError):
                        note = "Execution error: permission denied. " + text
                    else:
                        note = "Execution error: the tool failed. " + text
                    context.add_message(Message(
                        role=MessageRole.TOOL,
                        content=note,
                        tool_call_id=call.id,
                        name=call.name,
                    ))
                    continue

                if self._stop_requested(context) or getattr(result, "stop_reason", "") == "cancelled":
                    logger.info("Stop requested after tool %s", call.name)
                    return self._finish(context, "Stopped by user.", "cancelled", "Stopped by user.")

                content = result.to_model_content() if hasattr(result, "to_model_content") else (result.human_readable or "")
                image = None
                output = getattr(result, "output", None)
                if isinstance(output, dict) and isinstance(output.get("image"), dict):
                    image = output.get("image")
                context.add_message(Message(
                    role=MessageRole.TOOL,
                    content=content,
                    tool_call_id=call.id,
                    name=tool.name,
                    metadata={"images": [image]} if image else None,
                ))
                if call.name == "update_plan":
                    plan = (context.metadata or {}).get("plan")
                    archive = (context.metadata or {}).get("plan_archive") or []
                    cb = getattr(self, "on_plan", None)
                    if callable(cb):
                        try:
                            cb(plan or [], archive)
                        except Exception:
                            logger.exception("on_plan failed")
                    self._pin_todo(context)

        return self._finish(
            context,
            "Reached maximum iterations (loop limit).",
            "max_iterations",
            f"Stopped after {self.max_iterations} iterations.",
        )