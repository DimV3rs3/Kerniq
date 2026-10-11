import logging
import re
import platform
from typing import List, Optional
from uuid import uuid4
from .orchestrator import Orchestrator
from .context import TaskContext
from ..interfaces.providers import ModelProvider
from ..tools.registry import ToolRegistry
from ..interfaces.models import Message, MessageRole

logger = logging.getLogger(__name__)

_SYS_WRAP = re.compile(
    r"^\s*\[System\]\s*(?P<sys>.*?)\s*\[User\]\s*(?P<user>.*)\s*$",
    re.S | re.I,
)

TASK_COMPLETED_TAG = "TASK_COMPLETED"


def host_shell_hint() -> str:
    system = platform.system().lower()
    if system == "windows":
        return (
            "Host OS: Windows. The run_command tool executes in PowerShell "
            "(not cmd.exe). Prefer PowerShell syntax: Get-Date, Get-ChildItem, "
            "Select-String, etc. Avoid bash-only constructs unless pwsh is available."
        )
    if system == "darwin":
        return "Host OS: macOS. The run_command tool executes in a POSIX shell (bash/zsh)."
    return "Host OS: Linux. The run_command tool executes in bash/sh."


def language_instruction(lang_key: str) -> str:
    from Kerniq.settings.ui_store import RESPONSE_LANGUAGES
    if not lang_key or lang_key == "auto":
        return (
            "Answer in the same language the user is writing in, "
            "unless they explicitly ask for another language."
        )
    name = RESPONSE_LANGUAGES.get(lang_key, lang_key)
    return (
        f"You MUST answer strictly in {name}. "
        f"All explanations, headings and final replies must be in {name}, "
        f"except unavoidable code identifiers and file paths."
    )


class Agent:
    def __init__(self, provider: ModelProvider, tool_registry: ToolRegistry):
        self.provider = provider
        self.tool_registry = tool_registry
        self.orchestrator = Orchestrator(provider, tool_registry)
        self.system_prompt: str = (
            "You are a helpful coding agent with filesystem, terminal and web tools. "
            "Work only inside the workspace. Prefer small, correct edits. "
            "You may call multiple tools in one turn (parallel tool_calls)."
        )
        self.response_language: str = "auto"

    async def run(
        self,
        task: str,
        workspace: Optional[str] = None,
        system_prompt: Optional[str] = None,
        history: Optional[List[Message]] = None,
        response_language: Optional[str] = None,
    ) -> str:
        sys_from_task = None
        user_task = task or ""
        m = _SYS_WRAP.match(user_task)
        if m:
            sys_from_task = (m.group("sys") or "").strip()
            user_task = (m.group("user") or "").strip()
            logger.warning("Stripped [System]/[User] wrapper from task")

        logger.info(
            "Starting agent task=%r hist=%s lang=%s",
            (user_task or "")[:160],
            len(history or []),
            response_language or self.response_language,
        )

        session_id = uuid4()
        task_id = uuid4()
        context = TaskContext(
            task_id=task_id,
            session_id=session_id,
            goal=user_task,
            workspace=workspace,
        )

        sys_text = (system_prompt if system_prompt is not None else self.system_prompt) or ""
        if sys_from_task and not (system_prompt or "").strip():
            sys_text = sys_from_task

        lang = response_language if response_language is not None else self.response_language
        extras = [
            host_shell_hint(),
            language_instruction(lang),
            (
                f"When the user request is fully answered and no more tool calls are needed, "
                f"end your FINAL message with a single line containing exactly: {TASK_COMPLETED_TAG} "
                f"(nothing after it). Do not put {TASK_COMPLETED_TAG} on intermediate turns."
            ),
            (
                "When you need several independent facts, emit multiple tool_calls in one assistant turn "
                "instead of calling tools one-by-one across turns."
            ),
            (
                "For non-trivial tasks: FIRST outline a short checklist of steps in your reasoning, "
                "then work through the checklist. Do not stop after a single tool call if more steps remain. "
                "Only finish when the checklist is done or blocked."
            ),
        ]
        for tip in extras:
            if tip and tip not in sys_text:
                sys_text = (sys_text.rstrip() + "\n\n" + tip).strip()

        if sys_text:
            context.add_message(Message(role=MessageRole.SYSTEM, content=sys_text))

        if history:
            for msg in history:
                if msg.role == MessageRole.SYSTEM:
                    continue
                context.add_message(msg)

        context.add_message(Message(role=MessageRole.USER, content=user_task))
        logger.info("Context messages (%s): %s", len(context.messages), [m.role.value for m in context.messages])

        try:
            result = await self.orchestrator.run(context)
            return result
        except Exception as e:
            logger.exception("Agent execution failed")
            return f"Error during execution: {e}"
