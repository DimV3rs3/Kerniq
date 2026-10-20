"""Claude Code CLI as a text model.

Auth is the local `claude` login (the binary path is the setting). The CLI is
started with ``--permission-mode plan`` and ``--max-turns 1`` so it does not
edit the workspace behind Kerniq's tool policy. It does not emit Kerniq
tool_calls.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...interfaces.errors import ErrorCode, ProviderError
from ...interfaces.models import Message, MessageRole, ModelRequest, ModelResponse
from ...interfaces.providers import ModelProvider

logger = logging.getLogger(__name__)

_ALIASES = [
    {"id": "sonnet", "name": "sonnet"},
    {"id": "opus", "name": "opus"},
    {"id": "haiku", "name": "haiku"},
]


class ClaudeCodeProvider(ModelProvider):
    def __init__(
        self,
        binary_path: str = "claude",
        *,
        model: Optional[str] = None,
        timeout: float = 600.0,
    ):
        self.binary_path = (binary_path or "claude").strip() or "claude"
        self.model = (model or "").strip() or None
        self.timeout = float(timeout or 600.0)

    @property
    def provider_id(self) -> str:
        return "claude_code"

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "tool_calls": False,
            "streaming": False,
            "vision": False,
            "reasoning": False,
        }

    def resolve_binary(self) -> Optional[str]:
        raw = self.binary_path
        path = Path(raw)
        if path.is_absolute() or raw.startswith("."):
            return str(path) if path.exists() else None
        return shutil.which(raw)

    async def list_models(self) -> List[Dict[str, Any]]:
        return list(_ALIASES)

    async def check_connection(self) -> bool:
        return self.resolve_binary() is not None

    def _prompt(self, request: ModelRequest) -> str:
        lines: List[str] = []
        lines.append(
            "You are answering inside Kerniq. Reply with the next assistant message only. "
            "Do not edit files yourself; Kerniq owns the tools. "
            "If you would call a tool, describe the intended call in plain text."
        )
        for msg in request.messages:
            role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
            body = msg.content or ""
            if msg.tool_calls:
                names = ", ".join(tc.name for tc in msg.tool_calls)
                body = f"{body}\n[tool_calls: {names}]".strip()
            lines.append(f"[{role}]\n{body}")
        return "\n\n".join(lines)

    async def generate(self, request: ModelRequest) -> ModelResponse:
        binary = self.resolve_binary()
        if not binary:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Claude Code binary not found: {self.binary_path}",
            )
        cmd = [
            binary,
            "-p",
            "--output-format",
            "text",
            "--permission-mode",
            "plan",
            "--max-turns",
            "1",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        prompt = self._prompt(request)
        try:
            extra = {}
            if sys.platform == "win32":
                extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **extra,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                "Claude Code timed out",
                original_exception=exc,
            ) from exc
        except FileNotFoundError as exc:
            raise ProviderError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"Claude Code binary not found: {self.binary_path}",
                original_exception=exc,
            ) from exc
        text = (out or b"").decode("utf-8", errors="replace").strip()
        err_text = (err or b"").decode("utf-8", errors="replace").strip()
        if proc.returncode not in (0, None) and not text:
            raise ProviderError(
                ErrorCode.PROVIDER_REQUEST_FAILED,
                f"Claude Code exited {proc.returncode}: {err_text[:500]}",
            )
        return ModelResponse(
            messages=[Message(role=MessageRole.ASSISTANT, content=text)],
            finish_reason="stop",
            metadata={"api": "claude_code", "stderr": err_text[:500]},
        )
