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


def powershell_command(command: str) -> str:
    """Windows PowerShell 5.1 rejects &&. Models still write it."""
    return (command or "").replace("&&", ";")

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


def _scrub_env(workspace: Path, *, host_freedom: bool = False, use_venv: bool = True) -> dict:
    """Drop credential-bearing variables before spawning a shell."""
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
        from Kerniq.server.homes import jail_root

        roots = []
        task = current_task()
        meta = getattr(task, "metadata", None) or {}
        if meta.get("external_read_only", True):
            roots = [str(item) for item in (meta.get("external_files") or []) if item]
        visible = [str(workspace)]
        jail = jail_root()
        if jail is not None:
            visible = [str(jail)]
        for real in (meta.get("attachment_aliases") or {}).values():
            if real:
                visible.append(str(real))
        env = apply_sandbox_env(
            env,
            workspace,
            external_roots=roots,
            confine=not host_freedom,
            visible_roots=visible,
            use_venv=use_venv,
        )
    except Exception as exc:
        logger.warning("Sandbox env was not applied: %s", exc)
    return env


def _hidden_spawn() -> dict:
    """Flags for a short helper process. A console window must not appear."""
    import sys

    if sys.platform != "win32":
        return {}
    try:
        from Kerniq.sandbox.proc import hidden_kwargs

        return hidden_kwargs()
    except Exception:
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}


def kill_tree_command(pid: int) -> list[str] | None:
    """Windows needs taskkill /T. POSIX kills the process group instead."""
    import sys

    if sys.platform == "win32":
        return ["taskkill", "/PID", str(int(pid)), "/T", "/F"]
    return None


def _kill_tree(process) -> None:
    """Stop the shell and every child. A bare kill leaves the Windows console up."""
    import os
    import signal
    import subprocess
    import sys

    pid = getattr(process, "pid", None)
    if not pid:
        try:
            process.kill()
        except Exception:
            pass
        return
    if sys.platform == "win32":
        command = kill_tree_command(pid)
        if command:
            try:
                subprocess.run(command, capture_output=True, timeout=8, check=False, **_hidden_spawn())
                return
            except Exception:
                pass
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            return
        except Exception:
            pass
    try:
        process.kill()
    except Exception:
        pass


async def _stop_process(process, comm) -> None:
    """Kill the child tree. communicate() is never awaited without a deadline.

    A shell that ignores the first kill used to sit on ``await comm`` forever,
    so the tool card stayed on "Waiting for a tool".
    """
    _kill_tree(process)
    if comm is not None and not comm.done():
        try:
            await asyncio.wait_for(comm, 2)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            comm.cancel()
            try:
                await asyncio.wait_for(comm, 1.5)
            except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                pass
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
            "Run a shell command. The shell starts in .kerniq-view, which contains "
            "only links: ./workspace, ./attachments, and ./downloads. "
            "It does not copy those folders. "
            "python and pip in this shell are the workspace sandbox .kerniq-venv. "
            "node, npm, and dotnet are the workspace language sandbox, not the copies installed on this computer. "
            "Do not use absolute paths, UNC paths, '..', sudo, or commands that inspect the host. "
            "To clone a Git repository, use git_clone. Do not clone with this shell. "
            "On Windows this is PowerShell (not cmd). On Linux/macOS this is bash/sh."
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
        from Kerniq.tools.deadline import tool_timeout_seconds

        configured = getattr(self, "cfg_default_timeout", 30)
        timeout = tool_timeout_seconds(arguments, fallback=configured)

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

        # Host freedom is decided before the symlink walk and before the
        # working-directory check. An open host may leave the workspace.
        open_host = False
        opener = getattr(self._security_policy, "host_is_open", None)
        if callable(opener):
            open_host = bool(opener())
        if not open_host:
            from ....security.command_guard import escaping_symlink

            escaped = escaping_symlink(self._workspace_root)
            if escaped:
                return ToolResult(
                    tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                    tool_id=self.tool_id,
                    status="error",
                    output="",
                    human_readable=(
                        "Refusing shell: a symlink leaves ./workspace. "
                        "Remove it before running commands."
                    ),
                    error="PERMISSION_DENIED",
                )

        # Working directory. An open host may use ``/`` or another drive.
        # ``.`` falls back to the workspace if the link view cannot be created.
        try:
            from Kerniq.security.pathmask import terminal_cwd

            cwd_abs = terminal_cwd(str(cwd_rel or "."), self._security_policy)
        except Exception:
            return ToolResult(
                tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                tool_id=self.tool_id,
                status="error",
                output="",
                human_readable="Path is outside ./workspace",
                error="PERMISSION_DENIED"
            )

        if not Path(cwd_abs).is_dir():
            shown = str(cwd_rel or ".").replace("\\", "/").strip() or "."
            return ToolResult(
                tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                tool_id=self.tool_id,
                status="error",
                success=False,
                output="",
                human_readable=(
                    f"Working directory does not exist: {shown}. "
                    "Use a directory that is already there, or '.' for the workspace."
                ),
                error="cwd does not exist",
            )

        logger.info(f"Executing command: {command} in {cwd_abs}")
        
        import sys
        import os
        import time
        call_id = getattr(context, "last_tool_call_id", "unknown")
        started = time.monotonic()
        # Prefer list form on Windows for simple commands is hard; use shell but isolate.
        # Venv off, or host freedom: the shell gets the host PATH.
        use_venv = bool(getattr(self._security_policy, "use_venv", True)) and not open_host
        kwargs = dict(
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_abs),
            env=_scrub_env(
                self._workspace_root,
                host_freedom=open_host or bool(getattr(self._security_policy, "host_freedom", False)),
                use_venv=use_venv,
            ),
        )
        # Ensure the spawned process never creates a visible window or attaches to a console.
        if sys.platform == "win32":
            kwargs["stdin"] = asyncio.subprocess.DEVNULL
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            # 0x10 is CREATE_NEW_CONSOLE. It forces a window and cancels CREATE_NO_WINDOW.
            kwargs["creationflags"] = flags
            try:
                info = subprocess.STARTUPINFO()
                info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                info.wShowWindow = 0
                kwargs["startupinfo"] = info
            except Exception:
                pass
        else:
            kwargs["start_new_session"] = True
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
                    powershell_command(command),
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
            from Kerniq.security.pathmask import scrub_for_model

            reveal = bool(getattr(self._security_policy, "host_freedom", False))
            stdout_str = scrub_for_model(stdout_str, workspace=self._workspace_root, reveal=reveal)
            stderr_str = scrub_for_model(stderr_str, workspace=self._workspace_root, reveal=reveal)
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
            from Kerniq.security.pathmask import scrub_for_model

            reveal = bool(getattr(self._security_policy, "host_freedom", False))
            note = scrub_for_model(str(e), workspace=self._workspace_root, reveal=reveal)
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                stop_reason="error",
                output="",
                human_readable=note,
                error=note,
                duration_seconds=time.monotonic() - started,
            )


def git_clone_url(raw: str) -> str:
    """https, http, git://, or owner/repo. SSH and local paths are refused."""
    text = (raw or "").strip()
    if not text or any(ch in text for ch in " \t\r\n\"'`"):
        raise ValueError("The repository must be one token: https://host/owner/repo.git or owner/repo.")
    lower = text.lower()
    if lower.startswith(("ssh://", "git@", "file:", "ftp:")):
        raise ValueError("git_clone accepts https, http, git://, or owner/repo. It does not use SSH or a local path.")
    if "://" not in text:
        if text.count("/") != 1 or ".." in text.split("/"):
            raise ValueError("Use owner/repo, or a full https URL.")
        owner, repo = text.split("/", 1)
        if repo.endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo or any(ch in owner + repo for ch in ":\\"):
            raise ValueError("Use owner/repo, or a full https URL.")
        return f"https://github.com/{owner}/{repo}.git"
    if not lower.startswith(("https://", "http://", "git://")):
        raise ValueError("git_clone accepts https, http, or git://.")
    from urllib.parse import urlparse

    parsed = urlparse(text)
    if parsed.username or parsed.password:
        raise ValueError("The URL must not contain a username or password.")
    if not parsed.hostname or not parsed.path or parsed.path.strip("/") == "":
        raise ValueError("That URL is not a repository.")
    return text


def git_clone_dest(workspace: Path, url: str, dest: str) -> Path:
    """A path inside the workspace. An existing non-empty folder is refused."""
    root = Path(workspace).resolve()
    raw = (dest or "").strip().replace("\\", "/")
    if not raw:
        leaf = url.rstrip("/").rsplit("/", 1)[-1]
        if leaf.endswith(".git"):
            leaf = leaf[:-4]
        raw = leaf or "repo"
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Destination must stay inside the workspace.")
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Destination must stay inside the workspace.") from exc
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ValueError("Destination already exists and is not empty.")
    return target


def _git_env() -> dict:
    """Host git on PATH, without credential variables."""
    import os

    env = {}
    keep = (
        "PATH", "SYSTEMROOT", "WINDIR", "PATHEXT", "HOME", "USERPROFILE",
        "HOMEDRIVE", "HOMEPATH", "TMP", "TEMP", "TMPDIR", "LANG", "LC_ALL",
        "LC_CTYPE", "SSL_CERT_FILE", "SSL_CERT_DIR", "GIT_SSL_CAINFO",
        "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
    )
    for key in keep:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


class GitCloneTool(Tool):
    def __init__(self, workspace: str):
        self._workspace = Path(workspace)

    @property
    def tool_id(self) -> str:
        return "git_clone"

    @property
    def name(self) -> str:
        return "git_clone"

    @property
    def description(self) -> str:
        return (
            "Clone a Git repository into the workspace. "
            "Use this instead of run_command and instead of downloading a source archive. "
            "url is an https, http, or git:// address, or owner/repo (that becomes https://github.com/owner/repo.git). "
            "dest is optional and must stay inside the workspace. The default folder is the repository name. "
            "depth defaults to 1. Pass 0 for the full history. branch is optional. "
            "SSH URLs and local paths are refused."
        )

    @property
    def risk_level(self) -> str:
        return "medium"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "https URL, git:// URL, or owner/repo"},
                "dest": {"type": "string", "description": "Folder inside the workspace. Default is the repository name."},
                "branch": {"type": "string", "description": "Branch or tag to check out."},
                "depth": {"type": "integer", "description": "History depth. 1 is the default. 0 clones the full history.", "default": 1},
            },
            "required": ["url"],
        }

    @property
    def category(self) -> str:
        return "git"

    @property
    def pack_id(self) -> str:
        return "git"

    @property
    def ui_icon(self) -> str:
        return "git"

    @property
    def display_phrase(self) -> str:
        return "repos cloned"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        import sys

        call_id = getattr(context, "last_tool_call_id", "unknown")
        started = time.monotonic()
        try:
            url = git_clone_url(str((arguments or {}).get("url") or ""))
            target = git_clone_dest(self._workspace, url, str((arguments or {}).get("dest") or ""))
        except ValueError as exc:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                output="",
                human_readable=str(exc),
                error="INVALID_ARGS",
            )
        branch = str((arguments or {}).get("branch") or "").strip()
        if branch and (branch.startswith("-") or ".." in branch or any(ch in branch for ch in " \t\r\n\\")):
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                output="",
                human_readable="Branch must be a single name without spaces.",
                error="INVALID_ARGS",
            )
        try:
            depth = int((arguments or {}).get("depth", 1))
        except (TypeError, ValueError):
            depth = 1
        if depth < 0:
            depth = 0
        if depth > 1000:
            depth = 1000
        argv = ["git", "clone", "--quiet"]
        if depth > 0:
            argv.extend(["--depth", str(depth)])
        if branch:
            argv.extend(["--branch", branch])
        into_existing = target.exists()
        if into_existing:
            argv.extend(["--", url, "."])
            cwd = str(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            argv.extend(["--", url, str(target)])
            cwd = str(self._workspace.resolve())
        from Kerniq.tools.deadline import tool_timeout_seconds

        timeout = tool_timeout_seconds(arguments, fallback=180)
        if timeout < 30:
            timeout = 30
        if timeout > 600:
            timeout = 600
        kwargs = dict(
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=_git_env(),
        )
        if sys.platform == "win32":
            kwargs["stdin"] = asyncio.subprocess.DEVNULL
            flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            kwargs["creationflags"] = flags
            try:
                info = subprocess.STARTUPINFO()
                info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                info.wShowWindow = 0
                kwargs["startupinfo"] = info
            except Exception:
                pass
        else:
            kwargs["start_new_session"] = True
        try:
            process = await asyncio.create_subprocess_exec(*argv, **kwargs)
        except FileNotFoundError:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                output="",
                human_readable="git was not found on PATH. Install Git and try git_clone again. Do not use the shell.",
                error="git not found",
                duration_seconds=time.monotonic() - started,
            )
        try:
            waited = await _wait_command(process, timeout, context, started)
        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id=call_id,
                tool_id=self.tool_id,
                status="error",
                success=False,
                stop_reason="timeout",
                output="",
                human_readable=f"git clone timed out after {int(timeout)} seconds.",
                error="timeout",
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
                human_readable="git clone was stopped.",
                error="cancelled",
                duration_seconds=time.monotonic() - started,
            )
        stdout, stderr = waited
        text = (stderr or stdout or b"").decode("utf-8", errors="replace").strip()
        if len(text) > 4000:
            text = text[:4000] + "…"
        ok = process.returncode == 0
        shown = str(target.relative_to(self._workspace.resolve())).replace("\\", "/")
        if ok:
            note = f"Cloned into {shown}."
        else:
            note = text or f"git clone failed with exit {process.returncode}."
        return ToolResult(
            tool_call_id=call_id,
            tool_id=self.tool_id,
            status="success" if ok else "error",
            success=ok,
            output={"path": shown, "url": url, "exit_code": process.returncode},
            human_readable=note,
            error=None if ok else note,
            duration_seconds=time.monotonic() - started,
        )
