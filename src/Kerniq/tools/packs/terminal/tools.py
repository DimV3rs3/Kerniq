import asyncio
import contextlib
import logging
import subprocess
import time
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
    try:
        from Kerniq.sandbox.venv import apply_sandbox_env
        from Kerniq.security.task_scope import current_task

        roots = []
        task = current_task()
        meta = getattr(task, "metadata", None) or {}
        if meta.get("external_read_only", True):
            roots = [str(item) for item in (meta.get("external_files") or []) if item]
        env = apply_sandbox_env(env, workspace, external_roots=roots)
    except Exception as exc:
        logger.warning("Sandbox env was not applied: %s", exc)
    return env


async def _stop_process(process, comm) -> None:
    """Kill the child and let communicate() reap it. Do not wait() beside communicate()."""
    try:
        process.kill()
    except ProcessLookupError:
        pass
    except Exception:
        pass
    if comm is not None and not comm.done():
        try:
            await asyncio.wait_for(comm, 2)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            comm.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await comm
        except Exception:
            pass
    elif getattr(process, "returncode", None) is None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(process.wait(), 2)
    transport = getattr(process, "_transport", None)
    if transport is not None:
        with contextlib.suppress(Exception):
            transport.close()


async def _wait_command(process, timeout: float, context, started: float):
    """Wait for a shell. Returns (stdout, stderr), or None if the user stopped it.

    Polls `context.cancelled` so Stop does not wait for the timeout.
    """
    comm = asyncio.create_task(process.communicate())
    try:
        while not comm.done():
            if getattr(context, "cancelled", False):
                await _stop_process(process, comm)
                return None
            remaining = float(timeout) - (time.monotonic() - started)
            if remaining <= 0:
                await _stop_process(process, comm)
                raise asyncio.TimeoutError()
            try:
                await asyncio.wait_for(asyncio.shield(comm), timeout=min(0.25, remaining))
            except asyncio.TimeoutError:
                continue
        return comm.result()
    except asyncio.CancelledError:
        await _stop_process(process, comm)
        raise


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
            "python and pip in this shell are the workspace sandbox .kerniq-venv. "
            "The shell cannot see programs installed on this computer "
            "(dotnet, node, cmd, or the system PATH). "
            "Do not use Docker for Python tests. "
            "Absolute paths, UNC paths, '..', encoded PowerShell, and network utilities are denied. "
            "On Windows this is PowerShell (not cmd). On Linux/macOS this is bash/sh. "
            "Examples (Windows): Get-Date; Get-ChildItem . Examples (Unix): date; ls -la."
        )

    @property
    def risk_level(self) -> str:
        return "critical"

    def plan_membership_default(self) -> bool:
        return False

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

    @property
    def display_phrase(self) -> str:
        return "commands"

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
            env=_scrub_env(self._workspace_root),
        )
        # Ensure the spawned process never creates a visible window or attaches to a console.
        if sys.platform == "win32":
            kwargs["stdin"] = asyncio.subprocess.DEVNULL
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # Additionally hide any possible console window that might be opened by PowerShell.
            kwargs["creationflags"] = flags | 0x00000010  # DETACHED_PROCESS
        try:
            import shlex
            if sys.platform == "win32":
                # The shell binary is the host PowerShell. Its PATH is only the sandbox,
                # so the command itself cannot see dotnet, node, or cmd.
                windir = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows"
                ps_exe = os.path.join(windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
                if not os.path.isfile(ps_exe):
                    ps_exe = "powershell.exe"
                ps = [
                    ps_exe,
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy", "Bypass",
                    "-Command",
                    command,
                ]
                process = await asyncio.create_subprocess_exec(*ps, **kwargs)
            else:
                # On POSIX we use a plain shell but suppress any pseudo‑tty allocation that could bring up a terminal.
                process = await asyncio.create_subprocess_shell(command, **kwargs)
            try:
                waited = await _wait_command(process, float(timeout), context, started)
            except asyncio.TimeoutError:
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
            if waited is None:
                return ToolResult(
                    tool_call_id=call_id,
                    tool_id=self.tool_id,
                    status="error",
                    success=False,
                    stop_reason="cancelled",
                    output="",
                    human_readable="Stopped by user.",
                    error="cancelled",
                    duration_seconds=time.monotonic() - started,
                )
            stdout, stderr = waited

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
