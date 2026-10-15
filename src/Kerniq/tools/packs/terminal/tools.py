import asyncio
import subprocess
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from ....interfaces.tools import Tool, ToolResult
from ....interfaces.settings_schema import SettingsSchema, SettingField, SettingType
from ....security.policy import SecurityPolicy

logger = logging.getLogger(__name__)

_SECRET_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "CREDENTIAL",
    "AWS_SECRET",
    "AWS_ACCESS",
    "GITHUB",
    "PRIVATE_KEY",
    "DATABASE_URL",
)


def _scrub_env(workspace: Path) -> dict:
    """Drop credential-bearing variables before spawning a shell. PATH stays."""
    import os

    env = dict(os.environ)
    for key in list(env):
        upper = key.upper()
        if any(marker in upper for marker in _SECRET_MARKERS):
            env.pop(key, None)
    env["KERNIQ_WORKSPACE"] = str(workspace)
    return env


class TerminalTools(Tool):
    def __init__(self, workspace_root: Path, security_policy: SecurityPolicy):
        self._workspace_root = workspace_root
        self._security_policy = security_policy

    @property
    def tool_id(self) -> str:
        return "run_command"

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return (
            "Run a shell command in the workspace. "
            "Absolute paths, UNC paths, '..', encoded PowerShell, and network utilities are denied. "
            "On Windows this is PowerShell (not cmd). On Linux/macOS this is bash/sh. "
            "Examples (Windows): Get-Date; Get-ChildItem . Examples (Unix): date; ls -la."
        )

    @property
    def risk_level(self) -> str:
        return "critical"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to execute"},
                "cwd": {"type": "string", "description": "Working directory relative to workspace root"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30}
            },
            "required": ["command"]
        }

    @property
    def category(self) -> str:
        return "terminal"

    @property
    def pack_id(self) -> str:
        return "terminal"

    @property
    def ui_icon(self) -> str:
        return "💻"

    @property
    def collapsible(self) -> bool:
        return False

    def chat_label(self, count: int = 1, *, success: bool = True) -> str:
        return f"{count} команд"

    def settings_schema(self):
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="default_timeout", label="Default timeout (sec)", type=SettingType.INT, default=30, minimum=1, maximum=3600),
                SettingField(key="max_output_chars", label="Max output chars", type=SettingType.INT, default=50000, minimum=1000, maximum=500000),
            ],
        )

    def apply_settings(self, values):
        if not values:
            return
        self.cfg_default_timeout = int(values.get("default_timeout", getattr(self, "cfg_default_timeout", 30)))
        self.cfg_max_output_chars = int(values.get("max_output_chars", getattr(self, "cfg_max_output_chars", 50000)))

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        command = arguments.get("command")
        cwd_rel = arguments.get("cwd", ".")
        timeout = arguments.get("timeout", 30)

        # Security check for command content (paths, obfuscation, blacklist).
        # This runs even if an approval provider already said yes.
        block = self._security_policy.terminal_block_reason(str(command or ""))
        if block:
            return ToolResult(
                tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                tool_id=self.tool_id,
                status="error",
                output="",
                human_readable=block,
                error="PERMISSION_DENIED"
            )

        from ....security.command_guard import escaping_symlink

        escaped = escaping_symlink(self._workspace_root)
        if escaped:
            return ToolResult(
                tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                tool_id=self.tool_id,
                status="error",
                output="",
                human_readable=(
                    f"Refusing shell: symlink escapes the workspace ({escaped}). "
                    "Remove it before running commands."
                ),
                error="PERMISSION_DENIED",
            )

        # Security check for working directory
        try:
            cwd_abs = self._security_policy.validate_path(cwd_rel)
        except Exception as e:
            return ToolResult(
                tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                tool_id=self.tool_id,
                status="error",
                output="",
                human_readable=str(e),
                error="PERMISSION_DENIED"
            )

        logger.info(f"Executing command: {command} in {cwd_abs}")
        
        import sys
        import os
        import time
        call_id = getattr(context, "last_tool_call_id", "unknown")
        started = time.monotonic()
        # Prefer list form on Windows for simple commands is hard; use shell but isolate.
        kwargs = dict(
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_abs),
            env=_scrub_env(cwd_abs),
        )
        if sys.platform == "win32":
            # Prevent interactive hangs from inheriting console input (e.g. bare `date`)
            kwargs["stdin"] = asyncio.subprocess.DEVNULL
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            import shlex
            if sys.platform == "win32":
                # PowerShell — avoids cmd.exe quirks and interactive `date` hangs
                ps = [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    command,
                ]
                process = await asyncio.create_subprocess_exec(*ps, **kwargs)
            else:
                process = await asyncio.create_subprocess_shell(command, **kwargs)
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=float(timeout))
            except asyncio.TimeoutError:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
                return ToolResult(
                    tool_call_id=call_id,
                    tool_id=self.tool_id,
                    status="error",
                    success=False,
                    stop_reason="timeout",
                    output="",
                    human_readable=f"Command timed out after {timeout}s and was killed.",
                    error=f"timeout after {timeout}s",
                    duration_seconds=time.monotonic() - started,
                )

            exit_code = process.returncode
            def _decode_out(b: bytes) -> str:
                if not b:
                    return ""
                for enc in ("utf-8", "cp866", "cp1251", "latin-1"):
                    try:
                        return b.decode(enc)
                    except Exception:
                        continue
                return b.decode("utf-8", errors="replace")
            stdout_str = _decode_out(stdout or b"")
            stderr_str = _decode_out(stderr or b"")
            # Cap output
            max_out = getattr(self, "cfg_max_output_chars", 50_000)
            if len(stdout_str) > max_out:
                stdout_str = stdout_str[:max_out] + "…[truncated]"
            if len(stderr_str) > max_out:
                stderr_str = stderr_str[:max_out] + "…[truncated]"
            ok = exit_code == 0
            out_obj = {"exit_code": exit_code, "stdout": stdout_str, "stderr": stderr_str}
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="success" if ok else "error",
                success=ok,
                stop_reason="completed" if ok else "error",
                output=out_obj,
                human_readable=(stdout_str or stderr_str or f"exit {exit_code}")[:2000],
                error=None if ok else (stderr_str.strip() or f"exit code {exit_code}"),
                duration_seconds=time.monotonic() - started,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                stop_reason="error",
                output="",
                human_readable=str(e),
                error=str(e),
                duration_seconds=time.monotonic() - started,
            )
