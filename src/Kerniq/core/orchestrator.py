import json
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from .context import TaskContext
from ..interfaces.models import ModelRequest, ModelResponse, Message, MessageRole, ToolCall, GenerationOptions
from ..interfaces.providers import ModelProvider
from ..tools.registry import ToolRegistry
from ..security.policy import SecurityPolicy, PolicyDecision
from .verifier import Verifier

logger = logging.getLogger(__name__)

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
        self.generation_options = GenerationOptions()


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


    _TRUNC_MARK = "[Context truncated to fit the model window."
    _EMPTY_NUDGE = "Your last reply was empty. Provide a final answer or call a different tool."

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

    def _message_groups(self, messages):
        """Split non-system messages into atomic groups for safe trimming.

        A group is either:
        - one user message
        - one assistant message (optionally with tool_calls) + following tool results
        - orphan tool messages (will be dropped by sanitize)
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
        """Keep primary system + newest complete dialogue groups under budget."""
        messages = self._strip_truncation_notices(list(messages))
        if budget_tokens <= 0:
            return messages
        if self._estimate_tokens(messages) <= budget_tokens:
            return messages

        systems = [m for m in messages if m.role == MessageRole.SYSTEM]
        primary_system = systems[:1] if systems else []
        rest = [m for m in messages if m.role != MessageRole.SYSTEM]
        groups = self._message_groups(rest)

        kept_rev = []
        used = self._estimate_tokens(primary_system)
        for g in reversed(groups):
            cost = self._estimate_tokens(g)
            if used + cost > budget_tokens and kept_rev:
                break
            # always try to keep at least one group
            kept_rev.append(g)
            used += cost

        kept = []
        for g in reversed(kept_rev):
            kept.extend(g)

        # Hard-truncate oversized tool payloads inside kept groups
        for m in kept:
            if m.role == MessageRole.TOOL and m.content and len(m.content) > 12000:
                m.content = m.content[:12000] + "\n…[tool output truncated]"

        note = Message(
            role=MessageRole.SYSTEM,
            content=(
                self._TRUNC_MARK
                + " Older turns were dropped as complete groups; "
                "goals and recent tool results were prioritized.]"
            ),
        )
        return primary_system + [note] + kept

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
        """Ask model to continue without breaking role alternation (use user, not system)."""
        context.add_message(Message(
            role=MessageRole.USER,
            content=self._EMPTY_NUDGE,
        ))

    async def run(self, context: TaskContext) -> str:
        iteration = 0
        # Loop protection: identical tool-call signatures in a row
        last_tool_sig: Optional[str] = None
        tool_streak = 0
        empty_retries = 0
        content_loop_hits = 0
        assistant_history: list = []
        # Context budget (tokens). Prefer explicit option, else safe default.
        ctx_limit = None
        if self.generation_options and getattr(self.generation_options, "max_tokens", None):
            # generation max_tokens is output budget; input window is separate
            pass
        ctx_limit = int(getattr(self, "context_limit", 0) or 0) or int(
            (context.metadata or {}).get("context_limit") or 0
        ) or 32768
        # leave headroom for reply + tools
        # Leave room for model reply; never use a tiny budget that nukes history
        input_budget = max(4096, int(ctx_limit * 0.85)) if ctx_limit else 32000

        while iteration < self.max_iterations:
            if getattr(context, "cancelled", False):
                logger.info("Orchestration cancelled")
                return "Stopped by user."
            iteration += 1
            logger.info(f"Orchestration iteration {iteration}/{self.max_iterations}")

            # Fit messages into model context window (strip prior trim notes first)
            context.messages = self._strip_truncation_notices(context.messages)
            est = self._estimate_tokens(context.messages)
            # Only trim when clearly over budget (10% headroom already in input_budget)
            if est > input_budget:
                before = len(context.messages)
                context.messages = self._trim_messages_to_budget(context.messages, input_budget)
                logger.warning(
                    "Context overflow: %s msgs -> %s (est=%s budget=%s)",
                    before, len(context.messages), est, input_budget,
                )

            # 1. Prepare request — sanitize role order for strict chat templates
            safe_messages = self._sanitize_for_provider(context.messages)
            if not any(m.role == MessageRole.USER for m in safe_messages):
                # History collapse lost the user turn — re-anchor on the goal
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

            request = ModelRequest(
                messages=safe_messages,
                session_id=context.session_id,
                tools=self.tool_registry.get_tools_for_model(),
                options=self.generation_options,
            )

            # 2. Get model response
            response = await self.provider.generate(request)

            # Content loop detection on assistant text before committing tools
            for msg in response.messages:
                text = (msg.content or "").strip()
                if text and self._detect_content_loop(text, assistant_history):
                    content_loop_hits += 1
                    logger.warning("Content loop detected (hit=%s)", content_loop_hits)
                    if content_loop_hits >= 2:
                        return (
                            "Stopped: the model started repeating the same reasoning/answer "
                            "(loop protection)."
                        )
                    # One chance: nudge to stop repeating
                    context.add_message(Message(
                        role=MessageRole.SYSTEM,
                        content=(
                            "You are repeating previous content. Do not restate the same "
                            "reasoning. Either call a different tool or give a final concise answer."
                        ),
                    ))
                    # still add the message but continue loop without treating as final
                if text:
                    assistant_history.append(text)

            # Add assistant message to context (skip empty no-tool placeholders)
            for msg in response.messages:
                if msg.role == MessageRole.ASSISTANT and not (msg.content or "").strip() and not msg.tool_calls:
                    continue
                context.add_message(msg)

            # 3. Check for tool calls
            tool_calls = []
            for msg in response.messages:
                if msg.tool_calls:
                    tool_calls.extend(msg.tool_calls)

            if not tool_calls:
                # Before finishing, try to verify the result if a verifier is present
                if self.verifier:
                    verification = await self.verifier.verify(context.goal, context, context.workspace)
                    if not verification.passed:
                        logger.info(f"Verification failed: {verification.message}")
                        # We can add the verification failure to context and let the model try again
                        context.add_message(Message(
                            role=MessageRole.SYSTEM, 
                            content=f"Verification failed: {verification.message}. Please correct the result."
                        ))
                        continue # Try another iteration

                final_msg = response.messages[-1] if response.messages else None
                content = (final_msg.content if final_msg else "") or ""
                # Remove trailing empty assistant already added from response
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
                    return "Stopped: model returned empty responses repeatedly."
                empty_retries = 0
                return content

            # Loop guard: same tool+args repeated
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
                logger.warning(
                    "Identical tool streak=%s sig=%s — stopping loop",
                    tool_streak, sig[:200],
                )
                return (
                    "Stopped: the model repeated the same tool call(s) "
                    f"{tool_streak} times in a row (loop protection)."
                )

            # 4. Execute tool calls
            for call in tool_calls:
                logger.info(f"Executing tool: {call.name} with args {call.arguments}")
                
                # Security Check
                if self.security_policy:
                    decision = self.security_policy.evaluate_tool_call(call.name, call.arguments, "medium")
                    if decision == PolicyDecision.DENY:
                        error_msg = f"Security Error: Execution of tool {call.name} is denied by policy."
                        context.add_message(Message(
                            role=MessageRole.TOOL, 
                            content=error_msg, 
                            tool_call_id=call.id
                        ))
                        continue
                    elif decision == PolicyDecision.REQUIRE_APPROVAL:
                        if self.approval_provider:
                            from ..interfaces.approvals import ApprovalRequest
                            import uuid
                            from datetime import datetime
                            
                            app_req = ApprovalRequest(
                                request_id=uuid.uuid4(),
                                tool_id=call.name,
                                arguments=call.arguments,
                                risk_level="medium",
                                description=f"Executing {call.name}",
                                timestamp=datetime.utcnow().isoformat()
                            )
                            app_res = await self.approval_provider.request_approval(app_req)
                            if app_res.decision == "deny":
                                error_msg = f"Security Error: Tool {call.name} was denied by user: {app_res.comment}"
                                context.add_message(Message(
                                    role=MessageRole.TOOL, 
                                    content=error_msg, 
                                    tool_call_id=call.id
                                ))
                                continue
                        else:
                            error_msg = f"Security Error: Tool {call.name} requires manual approval but no provider is configured."
                            context.add_message(Message(
                                role=MessageRole.TOOL, 
                                content=error_msg, 
                                tool_call_id=call.id
                            ))
                            continue

                tool = self.tool_registry.get_tool(call.name)
                if not tool:
                    error_msg = f"Tool {call.name} not found"
                    context.add_message(Message(
                        role=MessageRole.TOOL, 
                        content=error_msg, 
                        tool_call_id=call.id
                    ))
                    continue

                # Execute tool
                result = await tool.execute(call.arguments, context)
                
                # Structured result for the model
                content = result.to_model_content() if hasattr(result, "to_model_content") else (result.human_readable or "")
                context.add_message(Message(
                    role=MessageRole.TOOL,
                    content=content,
                    tool_call_id=call.id,
                    name=tool.name,
                ))

        return "Reached maximum iterations (loop limit)."
