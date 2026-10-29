"""Cursor-like Web UI plugin — explorer, editor, chat, settings tabs."""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import sys
import threading
import time
import uuid
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.plugins.manifest import PluginManifest
from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType

# The explorer tree has no entry cap. To keep a huge workspace from burning CPU on the UI's 2.5 s poll,
# a finished walk is reused for 10x the time it took (at most 30 s). Requests with ?fresh=1 (the UI sends
# them after its own file operations and on manual refresh) always walk again.
_TREE_CACHE: Dict[str, Any] = {}
_TREE_LOCK = threading.Lock()

logger = logging.getLogger("plugin.web_ui")


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
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _ui_pid_path(context: Any) -> Optional[Path]:
    cfg = getattr(context, "config", None)
    state = getattr(getattr(cfg, "storage", None), "state_dir", None)
    if not state:
        return None
    return Path(state) / "ui.pid"


def _write_ui_pid(context: Any) -> None:
    path = _ui_pid_path(context)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"pid": os.getpid(), "role": "kerniq-web-ui"}),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("could not write ui.pid")


def _clear_ui_pid(context: Any) -> None:
    path = _ui_pid_path(context)
    if path is None or not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if int(data.get("pid") or 0) != os.getpid():
            return
        path.unlink()
    except Exception:
        logger.exception("could not remove ui.pid")

_BLOCKED_ATTACH = {
    "svg", "ico", "heic", "heif", "tif", "tiff",
    "mp4", "mov", "mkv", "webm", "avi", "wmv", "m4v", "mpg", "mpeg",
    "mp3", "wav", "ogg", "flac", "aac", "m4a", "wma", "opus",
    "exe", "dll", "bin", "iso", "dmg", "msi",
    "zip", "7z", "rar", "gz", "tar", "bz2", "xz",
}


def _is_junk_model(model: Dict[str, Any]) -> bool:
    """Embeddings and rerankers are not chat models."""
    kind = str(model.get("type") or "").lower()
    name = str(model.get("id") or model.get("name") or "").lower()
    if kind in ("embedding", "embeddings", "reranker"):
        return True
    return any(tok in name for tok in ("embed", "embedding", "rerank"))


def _heuristic_title(text: str) -> str:
    words = [w for w in (text or "").replace("\n", " ").split() if w][:3]
    return " ".join(words) or "Chat"


def _model_ids_match(a: str, b: str) -> bool:
    """Exact id only. A shorter sibling is a different model."""
    from Kerniq.models.identity import same_model

    return same_model(a, b)


def _clean_title(raw: str) -> str:
    line = (raw or "").strip().splitlines()[0].strip().strip("\"'").strip() if raw else ""
    if not line or len(line) > 80:
        return ""
    noisy = sum(ch.isdigit() or ch in ".,-eE" for ch in line)
    if noisy > len(line) * 0.5:
        return ""
    words = line.split()
    if len(words) > 6:
        line = " ".join(words[:4])
    return line


async def _title_from_loaded_model(provider, model_id: str, text: str) -> tuple:
    """Ask one already-loaded model for a short title. Restores provider.model.

    Returns (title, model id that actually answered). An empty title and a
    mismatched id are both discarded by the caller.
    """
    from uuid import uuid4

    from Kerniq.interfaces.models import GenerationOptions, Message, MessageRole, ModelRequest

    saved = getattr(provider, "model", None)
    provider.model = model_id
    try:
        request = ModelRequest(
            messages=[
                Message(
                    role=MessageRole.SYSTEM,
                    content="Reply with a chat title of at most four words. No quotes.",
                ),
                Message(role=MessageRole.USER, content=(text or "")[:500]),
            ],
            session_id=uuid4(),
            tools=None,
            options=GenerationOptions(
                temperature=0.2,
                max_tokens=16,
                streaming=False,
                extra_params={"enable_thinking": False, "thinking": {"type": "disabled"}},
            ),
            metadata={"kerniq_internal": "title", "model": model_id},
        )
        response = await provider.generate(request)
    except Exception as exc:
        logger.info("embedding model did not return a title: %s", exc)
        return "", ""
    finally:
        provider.model = saved
    raw = ""
    if response and response.messages:
        raw = response.messages[0].content or ""
    answered = ""
    meta = getattr(response, "metadata", None) or {}
    if isinstance(meta, dict):
        answered = str(meta.get("model") or "").strip()
    return _clean_title(raw), answered


def _public_error(exc: BaseException) -> tuple[str, str]:
    raw = str(exc or "").strip() or exc.__class__.__name__
    low = raw.lower()
    if "timeout" in low or "timed out" in low:
        title = "The model did not answer in time."
    elif any(tok in low for tok in ("unreachable", "connection", "connect", "name or service", "network")):
        title = "The provider is unreachable. Check the address and the network."
    elif any(tok in low for tok in ("401", "403", "api key", "unauthorized", "authentication")):
        title = "The provider rejected the credentials."
    elif "loop" in low:
        title = "Stopped: the model was repeating itself."
    elif "unload" in low or "not loaded" in low or "no model" in low:
        title = "The model is not loaded."
    else:
        title = "The task stopped."
    return title, raw


def _extract_draft(text: str) -> str:
    raw = text or ""
    start = raw.find("===ACT_DRAFT===")
    end = raw.find("===END_DRAFT===")
    if start >= 0 and end > start:
        return raw[start + len("===ACT_DRAFT==="):end].strip()
    prose = raw.split("===ACT_DRAFT===")[0].strip()
    return prose[:4000]


def _strip_draft(text: str) -> str:
    raw = text or ""
    start = raw.find("===ACT_DRAFT===")
    if start < 0:
        return raw.strip()
    return raw[:start].strip()



def _detect_lan_ip() -> str:
    """Best-effort LAN IPv4 without urllib."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if ip and not str(ip).startswith("127."):
            return str(ip)
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if addr and not addr.startswith("127."):
                return addr
    except Exception:
        pass
    return "127.0.0.1"


def _parse_qs(path: str) -> tuple[str, Dict[str, str]]:
    if "?" not in path:
        return path, {}
    base, q = path.split("?", 1)
    out: Dict[str, str] = {}
    for part in q.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
        else:
            k, v = part, ""
        out[_pct_decode(k)] = _pct_decode(v)
    return base, out


def _pct_decode(s: str) -> str:
    """Decode percent-encoding to Unicode (UTF-8), safe for Cyrillic paths."""
    raw = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "%" and i + 2 < len(s):
            try:
                raw.append(int(s[i + 1 : i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        if s[i] == "+":
            raw.append(0x20)
            i += 1
            continue
        # ASCII / already-decoded chars → UTF-8 bytes
        raw.extend(s[i].encode("utf-8"))
        i += 1
    return raw.decode("utf-8", errors="replace")


class _State:
    context: Optional[PluginContext] = None
    host = "127.0.0.1"
    port = 8765
    server_mode = False
    server: Optional[ThreadingHTTPServer] = None
    runs: Dict[str, Dict[str, Any]] = {}
    runs_lock = threading.Lock()
    chat_histories: Dict[str, list] = {}
    chat_lock = threading.Lock()
    approvals = None
    chat_log = None
    # Chats whose Stop arrived before the run id existed.
    cancel_chats: set = set()
    # Absolute paths the file dialog on this process actually returned.
    granted_paths: set = set()
    jobs: Dict[str, Dict[str, Any]] = {}
    jobs_lock = threading.Lock()
    pending: list = []
    history = None


STATE = _State()
# Per request thread. Concurrent browsers must not share one global user id.
_ui_user: contextvars.ContextVar[str] = contextvars.ContextVar("kerniq_ui_user", default="")
from Kerniq.security.approval_broker import ApprovalBroker

STATE.approvals = ApprovalBroker()

_STOP_NOTE = (
    "Stopped by the user. This reply was not finished. "
    "Continue the same task from the work already done. Do not start over."
)


def _norm_visible(text: str) -> str:
    body = (text or "").strip()
    marker = "\n\n[kerniq] outcome="
    if marker in body:
        body = body.split(marker, 1)[0].strip()
    if body.endswith(_STOP_NOTE):
        body = body[: -len(_STOP_NOTE)].strip()
    return body


def _is_visible_row(row: dict) -> bool:
    role = row.get("role")
    return role in ("user", "assistant") and bool(str(row.get("content") or "").strip())


def _visible_equal(left: dict, right: dict) -> bool:
    if left.get("role") != right.get("role"):
        return False
    a = _norm_visible(str(left.get("content") or ""))
    b = _norm_visible(str(right.get("content") or ""))
    if not a or not b:
        return a == b
    return a == b or a.startswith(b) or b.startswith(a)


def transcript_rows(messages) -> list:
    """Model-facing turns. System notes stay out. Tool calls stay in."""
    rows = []
    for msg in messages or []:
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content") or ""
            calls = msg.get("tool_calls") or None
            tool_call_id = msg.get("tool_call_id")
            name = msg.get("name")
        else:
            role = getattr(getattr(msg, "role", None), "value", None) or str(getattr(msg, "role", "") or "")
            content = getattr(msg, "content", "") or ""
            calls = []
            for tc in getattr(msg, "tool_calls", None) or []:
                calls.append({
                    "id": str(getattr(tc, "id", "") or ""),
                    "name": str(getattr(tc, "name", "") or ""),
                    "arguments": getattr(tc, "arguments", None) or {},
                })
            calls = calls or None
            tool_call_id = getattr(msg, "tool_call_id", None)
            name = getattr(msg, "name", None)
        if role not in ("user", "assistant", "tool"):
            continue
        meta = msg.get("metadata") if isinstance(msg, dict) else getattr(msg, "metadata", None)
        if isinstance(meta, dict) and meta.get("kerniq_internal"):
            continue
        if role == "assistant" and not str(content).strip() and not calls:
            continue
        if role != "assistant" and not str(content).strip():
            continue
        row = {"role": role, "content": content}
        if calls:
            row["tool_calls"] = calls
        if tool_call_id:
            row["tool_call_id"] = tool_call_id
        if name:
            row["name"] = name
        if isinstance(meta, dict):
            images = [
                {"path": item.get("path"), "root": item.get("root"), "mime": item.get("mime")}
                for item in (meta.get("images") or [])
                if isinstance(item, dict) and item.get("path") and item.get("root")
            ]
            if images:
                row["metadata"] = {"images": images}
        rows.append(row)
    return rows


def _covers(longer: list, shorter: list) -> bool:
    long_vis = [row for row in longer if _is_visible_row(row)]
    short_vis = [row for row in shorter if _is_visible_row(row)]
    if len(long_vis) < len(short_vis):
        return False
    return all(_visible_equal(long_vis[i], short_vis[i]) for i in range(len(short_vis)))


def _collapse_consecutive_users(rows: list) -> list:
    """One send must not land as two identical user turns in a row."""
    out = []
    for row in rows or []:
        prev = out[-1] if out else None
        if (
            prev
            and prev.get("role") == "user"
            and row.get("role") == "user"
            and (prev.get("content") or "") == (row.get("content") or "")
            and not prev.get("tool_calls")
            and not row.get("tool_calls")
        ):
            continue
        out.append(row)
    return out


def merge_histories(server, client) -> list:
    """Keep the transcript the model should continue.

    The server copy can hold tool calls the browser does not send back.
    The browser copy can hold the turn the user just typed after Stop.
    A new user message is never dropped, and server tool calls are kept
    when the two copies still share a prefix.
    """
    server_rows = [dict(row) for row in (server or []) if isinstance(row, dict) and row.get("role")]
    client_rows = [
        dict(row)
        for row in (client or [])
        if isinstance(row, dict) and row.get("role") in ("user", "assistant", "tool")
    ]
    if not client_rows:
        return server_rows
    if not server_rows:
        return client_rows
    server_vis_idx = [i for i, row in enumerate(server_rows) if _is_visible_row(row)]
    client_vis = [row for row in client_rows if _is_visible_row(row)]
    matched = 0
    limit = min(len(server_vis_idx), len(client_vis))
    while matched < limit and _visible_equal(server_rows[server_vis_idx[matched]], client_vis[matched]):
        matched += 1
    if matched == 0:
        return _collapse_consecutive_users(client_rows if len(client_vis) >= len(server_vis_idx) else server_rows)
    if matched == len(client_vis):
        return _collapse_consecutive_users(server_rows)
    extra = []
    for row in client_vis[matched:]:
        if row.get("role") == "user":
            extra.append(dict(row))
            continue
        if row.get("role") != "assistant":
            continue
        tail = extra[-1] if extra else (server_rows[-1] if server_rows else None)
        if not tail or tail.get("role") != "assistant":
            extra.append(dict(row))
    return _collapse_consecutive_users(server_rows + extra)


def _mark_stopped(rows: list, partial: str) -> list:
    rows = [dict(row) for row in rows]
    partial = (partial or "").strip()
    if rows and rows[-1].get("role") == "assistant" and not rows[-1].get("tool_calls"):
        body = rows[-1].get("content") or ""
        if partial and partial not in body:
            body = (body.rstrip() + "\n" + partial).strip()
        if _STOP_NOTE not in body:
            body = (body.rstrip() + "\n\n" + _STOP_NOTE).strip() if body.strip() else _STOP_NOTE
        rows[-1]["content"] = body
        return rows
    text = partial
    if _STOP_NOTE not in text:
        text = (text.rstrip() + "\n\n" + _STOP_NOTE).strip() if text else _STOP_NOTE
    rows.append({"role": "assistant", "content": text})
    return rows


def compose_saved_history(prior, context_messages, *, user_task="", partial="", cancelled=False) -> list:
    """Full transcript for the next model call, including a stopped turn."""
    fresh = transcript_rows(context_messages)
    prior_rows = transcript_rows(prior)
    if fresh and _covers(fresh, prior_rows):
        rows = fresh
    elif fresh:
        rows = prior_rows + fresh
    else:
        rows = list(prior_rows)
        task = (user_task or "").strip()
        if task and not (rows and rows[-1].get("role") == "user" and (rows[-1].get("content") or "") == task):
            rows.append({"role": "user", "content": task})
    if cancelled:
        rows = _mark_stopped(rows, partial)
    rows = _collapse_consecutive_users(rows)
    if len(rows) > 200:
        rows = rows[-200:]
        while rows and rows[0].get("role") == "tool":
            rows.pop(0)
    return rows


def partial_assistant_text(events) -> str:
    """Text the UI already showed, after the last finished tool."""
    buf: list[str] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "content_delta":
            buf.append(event.get("text") or "")
        elif kind == "tool" and event.get("status") not in (None, "pending"):
            buf = []
        elif kind == "assistant" and str(event.get("content") or "").strip():
            buf = [str(event.get("content") or "")]
    return "".join(buf).strip()


def _todo_plan_ready(tools: list) -> bool:
    """Build-a-plan is available only when update_plan is enabled and in Plan mode."""
    for tool in tools or []:
        if not isinstance(tool, dict) or tool.get("name") != "update_plan":
            continue
        if tool.get("enabled") is False:
            return False
        values = tool.get("values") if isinstance(tool.get("values"), dict) else {}
        if "include_in_plan" in values:
            return bool(values.get("include_in_plan"))
        return bool(tool.get("include_in_plan"))
    return False


def _pack_rows_from(tools: list) -> list:
    from Kerniq.tools.loader import discover_pack_classes

    rows = []
    for cls in discover_pack_classes():
        try:
            pack = cls()
            schema = pack.settings_schema()
        except Exception:
            logger.exception("pack schema")
            continue
        members = [
            tool for tool in tools
            if (tool.get("pack_id") or tool.get("category")) == pack.pack_id
        ]
        enabled = any(tool.get("enabled") is not False for tool in members) if members else False
        values = {}
        fields = list(getattr(schema, "fields", None) or [])
        for field in fields:
            seen = []
            for tool in members:
                raw = (tool.get("values") or {})
                if field.key in raw:
                    seen.append(raw.get(field.key))
                else:
                    seen.append(field.default)
            if seen and all(item == seen[0] for item in seen):
                values[field.key] = seen[0]
            else:
                values[field.key] = None
        rows.append({
            "id": pack.pack_id,
            "name": pack.name,
            "description": pack.description,
            "enabled": enabled,
            "schema": schema.to_public() if schema else None,
            "values": values,
        })
    return rows


def history_message(row: dict):
    from Kerniq.interfaces.models import Message, MessageRole, ToolCall

    if not isinstance(row, dict):
        return None
    role = row.get("role")
    content = row.get("content") or ""
    if role not in ("user", "assistant", "tool"):
        return None
    meta = row.get("metadata")
    if isinstance(meta, dict) and meta.get("kerniq_internal"):
        return None
    calls = []
    for tc in row.get("tool_calls") or []:
        if not isinstance(tc, dict) or not tc.get("name"):
            continue
        args = tc.get("arguments") if isinstance(tc.get("arguments"), dict) else {}
        calls.append(ToolCall(id=str(tc.get("id") or uuid.uuid4()), name=str(tc["name"]), arguments=args))
    if role == "assistant" and not str(content).strip() and not calls:
        return None
    if role != "assistant" and not str(content).strip():
        return None
    images = None
    if isinstance(meta, dict):
        kept = [
            {"path": item.get("path"), "root": item.get("root"), "mime": item.get("mime")}
            for item in (meta.get("images") or [])
            if isinstance(item, dict) and item.get("path") and item.get("root")
        ]
        if kept:
            images = {"images": kept}
    return Message(
        role=MessageRole(role),
        content=content,
        tool_calls=calls or None,
        tool_call_id=row.get("tool_call_id") or None,
        name=row.get("name") or None,
        metadata=images,
    )


def _grant_path(path: str) -> None:
    try:
        STATE.granted_paths.add(str(Path(path).resolve()))
    except Exception:
        return


def _forbidden_grant(path: Path) -> bool:
    """Refuse the filesystem root and a few system trees. A chosen project folder is fine."""
    try:
        resolved = path.resolve()
    except OSError:
        return True
    posix = resolved.as_posix().rstrip("/") or "/"
    if posix in {"/", "/etc", "/usr", "/bin", "/sbin", "/proc", "/sys", "/dev", "/root", "/boot", "/lib", "/var"}:
        return True
    return resolved.parent == resolved


def _granted(path: str) -> bool:
    try:
        return str(Path(path).resolve()) in STATE.granted_paths
    except Exception:
        return False


def _json(handler: BaseHTTPRequestHandler, code: int, payload: Any) -> None:
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if getattr(handler, "_kerniq_set_cookie", False) and getattr(handler, "_kerniq_user", ""):
        from Kerniq.server.identity import cookie_header

        handler.send_header("Set-Cookie", cookie_header(handler._kerniq_user))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _state_dir() -> Path:
    cfg = getattr(getattr(STATE, "context", None), "config", None)
    storage = getattr(cfg, "storage", None)
    state = getattr(storage, "state_dir", None)
    if state:
        return Path(state)
    from Kerniq.settings.loader import SettingsProvider

    return Path(SettingsProvider().config.storage.state_dir)


def _server_core() -> dict:
    from Kerniq.server.settings import load_server_settings
    from Kerniq.settings.loader import SettingsProvider

    return load_server_settings(_state_dir(), SettingsProvider().config)


def _history_store():
    if STATE.history is not None:
        return STATE.history
    from Kerniq.server.store import open_history

    core = _server_core()
    STATE.history = open_history(_state_dir(), str(core.get("database_url") or ""))
    return STATE.history


def _identify(handler: BaseHTTPRequestHandler) -> tuple[str, str]:
    from Kerniq.server.identity import resolve_user

    core = _server_core() if STATE.server_mode else {}
    user_id, set_cookie, kind = resolve_user(
        handler.headers,
        server_mode=bool(STATE.server_mode),
        api_key=str(core.get("api_key") or ""),
    )
    handler._kerniq_user = user_id
    handler._kerniq_set_cookie = set_cookie
    handler._kerniq_kind = kind
    _ui_user.set(user_id)
    if STATE.server_mode and user_id:
        _arm_user_fs(user_id)
    return user_id, kind


def _arm_user_fs(user_id: str):
    """Pin this thread to one user folder and its disk limit."""
    from Kerniq.server.homes import bind_jail, quota_bytes, quota_status, set_quota, user_home

    core = _server_core()
    folder = user_home(_state_dir(), user_id, core)
    bind_jail(folder)
    set_quota(quota_status(folder, quota_bytes(core)))
    return folder


def _history_key(user_id: str, chat_id: str) -> str:
    if not STATE.server_mode:
        return chat_id
    return f"{user_id}\x1f{chat_id}"


def _settings_store():
    from Kerniq.settings.ui_store import UiSettingsStore
    from Kerniq.settings.loader import SettingsProvider

    cfg = SettingsProvider().config
    return UiSettingsStore(cfg.storage.state_dir)


def _langpacks():
    import importlib.util
    import sys
    name = "kerniq_web_ui_langpacks"
    if name in sys.modules:
        return sys.modules[name]
    path = Path(__file__).resolve().parent / "langpacks.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _workspace() -> Path:
    if STATE.server_mode:
        from Kerniq.server.homes import user_home

        return user_home(_state_dir(), _ui_user.get() or "local", _server_core())
    store = _settings_store()
    raw = Path(store.load().agent.workspace or "./workspace")
    if raw.is_absolute():
        return raw.expanduser().resolve()
    from Kerniq.devtools.paths import anchored_dir
    from Kerniq.server.homes import gather_stray_workspace

    return gather_stray_workspace(anchored_dir(raw), raw)


def _workspace_label(ws: Path) -> str:
    """What the browser may see. Never the machine path of a relative workspace."""
    if STATE.server_mode:
        return "/workspace"
    configured = str(_settings_store().load().agent.workspace or "./workspace").strip() or "./workspace"
    if Path(configured).is_absolute():
        return configured
    return configured



def _norm_rel(rel: str) -> str:
    """Normalize relative path from client (Unicode, separators)."""
    if not rel:
        return ""
    rel = rel.replace(chr(92), "/").strip()
    # remove leading ./
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def _safe(ws: Path, rel: str) -> Path:
    if STATE.server_mode:
        from Kerniq.server.homes import logical_path

        return logical_path(rel or ".", ws)
    rel = _norm_rel(rel)
    ws = ws.resolve()
    target = (ws / (rel or ".")).resolve()
    try:
        target.relative_to(ws)
    except ValueError as e:
        raise PermissionError("path outside workspace") from e
    return target


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("UI " + fmt, *args)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        _identify(self)
        path, qs = _parse_qs(self.path)
        if getattr(self, "_kerniq_kind", "") == "denied" and path.startswith("/api/"):
            return _json(self, 401, {"error": "The API key was rejected."})
        if path in ("/", "/index.html"):
            token = (qs.get("debug") or "").strip()
            if token and STATE.server_mode:
                from Kerniq.server.debug import set_cookie_header, token_matches

                if token_matches(_state_dir(), token):
                    self.send_response(302)
                    self.send_header("Location", "/")
                    self.send_header("Set-Cookie", set_cookie_header(token))
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
            return self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/static/app.js":
            return self._file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/static/styles.css":
            return self._file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if path.startswith("/static/brand/"):
            name = path.rsplit("/", 1)[-1]
            if name not in {
                "kerniq-mark.svg",
                "kerniq-tile.svg",
                "kerniq-white-out.svg",
                "kerniq-black-out.svg",
            }:
                return _json(self, 404, {"error": "not found"})
            return self._file(STATIC_DIR / "brand" / name, "image/svg+xml")
        if path.startswith("/static/vendor/"):
            name = path.rsplit("/", 1)[-1]
            safe = name.replace("-", "").replace("_", "").replace(".", "")
            if not safe.isalnum():
                return _json(self, 400, {"error": "bad path"})
            f = STATIC_DIR / "vendor" / name
            ctype = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
            return self._file(f, ctype)
        if path.startswith("/static/modules/"):
            name = path[len("/static/modules/") :]
            if "/" in name or ".." in name or not name.replace("-", "").replace("_", "").replace(".", "").isalnum():
                return _json(self, 400, {"error": "bad path"})
            if not (name.endswith(".js") or name.endswith(".css")):
                return _json(self, 404, {"error": "not found"})
            f = STATIC_DIR / "modules" / name
            ctype = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
            return self._file(f, ctype)
        if path == "/api/settings":
            from Kerniq.settings.browser import public_settings

            payload = _settings_store().load().model_dump()
            return _json(self, 200, public_settings(payload, server_mode=bool(STATE.server_mode)))
        if path == "/api/providers":
            from Kerniq.models.catalog import public_specs
            return _json(self, 200, {"providers": public_specs()})
        if path == "/api/languages":
            from Kerniq.settings.ui_store import RESPONSE_LANGUAGES
            return _json(self, 200, {"languages": RESPONSE_LANGUAGES})
        if path == "/api/ui/languages":
            from Kerniq.settings.loader import SettingsProvider
            state = SettingsProvider().config.storage.state_dir
            return _json(self, 200, {"packs": _langpacks().list_packs(state, with_strings=True)})
        if path == "/api/tools":
            return _json(self, 200, self._tools())
        if path == "/api/plugins":
            return _json(self, 200, self._plugins())
        if path == "/api/extensions":
            return _json(self, 200, self._extensions())
        if path == "/api/models":
            return _json(self, 200, self._models())
        if path == "/api/lms/loaded":
            return _json(self, 200, self._lms_loaded())
        if path == "/api/fs/tree":
            return _json(self, 200, self._tree(fresh=(qs.get("fresh") == "1")))
        if path == "/api/fs/file":
            return _json(self, 200, self._read_file(qs.get("path", "")))
        if path == "/api/fs/download":
            return self._download(qs.get("path", ""))
        if path == "/api/chat/events":
            return _json(self, 200, self._events(qs.get("run_id", ""), qs.get("cursor", "0")))
        if path == "/api/chat/snapshot":
            return _json(self, 200, self._snapshot(qs.get("chat_id", "")))
        if path == "/api/component/settings":
            return _json(self, 200, self._get_component_settings(qs))
        if path == "/api/components":
            return _json(self, 200, self._list_components())
        if path == "/api/server/info":
            return _json(self, 200, self._server_info())
        if path == "/api/fs/search":
            return _json(self, 200, self._search_files(qs.get("q", "")))
        if path == "/api/approvals":
            broker = STATE.approvals
            pending = broker.list_pending() if broker is not None else []
            return _json(self, 200, {"pending": pending})
        if path == "/api/ui/chats":
            return _json(self, 200, self._load_ui_chats())
        if path == "/api/remote/events":
            return self._remote_events(qs)
        if path == "/api/models/load-plan":
            return _json(self, 200, self._load_plan(qs.get("model", "")))
        if path == "/api/plugins/job":
            return _json(self, 200, self._plugin_job(qs.get("id", "")))
        if path == "/api/benchmark/active":
            return _json(self, 200, self._benchmark_active())
        if path == "/api/ui/autostart":
            from Kerniq.devtools.autostart import current
            from Kerniq.devtools.paths import find_project_root

            return _json(self, 200, current(project=find_project_root()))
        _json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        _identify(self)
        path, _ = _parse_qs(self.path)
        if getattr(self, "_kerniq_kind", "") == "denied":
            return _json(self, 401, {"error": "The API key was rejected."})
        data = _read_json(self)
        if path == "/api/settings":
            if STATE.server_mode:
                return _json(self, 200, {"ok": True, "stored": "browser", "client_owned": True})
            store = _settings_store()
            store.update(data)
            current = store.load()
            if current.chat.compose_plan and not _todo_plan_ready(self._list_components().get("tools") or []):
                current.chat.compose_plan = False
                store.save(current)
            return _json(self, 200, store.load().model_dump())
        if path == "/api/models":
            return _json(self, 200, self._models(data if isinstance(data, dict) else None))
        if path == "/api/chat/run":
            return _json(self, 200, self._start_run(data))
        if path == "/api/component/settings":
            return _json(self, 200, self._save_component_settings(data))
        if path == "/api/settings/reset":
            return _json(self, 200, self._reset_settings(data))
        if path == "/api/ui/languages/import":
            from Kerniq.settings.loader import SettingsProvider
            try:
                saved = _langpacks().import_pack(SettingsProvider().config.storage.state_dir, data.get("pack"))
            except ValueError as exc:
                body = {"error": str(exc)}
                errors = getattr(exc, "errors", None)
                if errors:
                    body["errors"] = list(errors)
                return _json(self, 400, body)
            return _json(self, 200, saved)
        if path == "/api/ui/languages/delete":
            from Kerniq.settings.loader import SettingsProvider
            ok = _langpacks().delete_pack(SettingsProvider().config.storage.state_dir, str((data or {}).get("id") or ""))
            return _json(self, 200, {"ok": ok})
        if path == "/api/fs/rename":
            return _json(self, 200, self._rename(data))
        if path == "/api/fs/reveal":
            return _json(self, 200, self._reveal(data))
        if path == "/api/fs/pick_folder":
            return _json(self, 200, self._pick_folder())
        if path == "/api/fs/pick_attach_folder":
            return _json(self, 200, self._pick_attach_folder())
        if path == "/api/fs/pick_files":
            return _json(self, 200, self._pick_files())
        if path == "/api/server/database":
            return _json(self, 200, self._save_database(data))
        if path == "/api/lms/load":
            return _json(self, 200, self._lms_load(data))
        if path == "/api/shutdown":
            return _json(self, 200, self._shutdown_server())
        if path == "/api/lms/unload_all":
            return _json(self, 200, self._lms_unload_all())
        if path == "/api/fs/create":
            return _json(self, 200, self._create_path(data))
        if path == "/api/attachments/import":
            return _json(self, 200, self._import_attachment(data))
        if path == "/api/chat/cancel":
            return _json(self, 200, self._cancel_run(data))
        if path == "/api/chat/title":
            return _json(self, 200, self._chat_title(data))
        if path == "/api/approvals/decide":
            broker = STATE.approvals
            if broker is None:
                return _json(self, 500, {"ok": False, "error": "approval broker missing"})
            return _json(
                self,
                200,
                broker.decide(
                    str((data or {}).get("request_id") or ""),
                    str((data or {}).get("decision") or ""),
                    (data or {}).get("comment"),
                ),
            )
        if path == "/api/plugins/action":
            return _json(self, 200, self._start_plugin_action(data))
        if path == "/api/plugins/search":
            from Kerniq.plugins.distribution import search_repositories

            found = search_repositories(str((data or {}).get("query") or ""), int((data or {}).get("limit") or 8))
            return _json(self, 200, found)
        if path == "/api/plugins/install":
            from Kerniq.plugins.distribution import install_github, install_tree

            force = bool((data or {}).get("force"))
            local = str((data or {}).get("path") or "").strip()
            repo = str((data or {}).get("repo") or "").strip()
            if local:
                result = install_tree(local, force=force, plugins_dir=self._plugins_dir())
            elif repo:
                result = install_github(repo, force=force, plugins_dir=self._plugins_dir())
            else:
                result = {"ok": False, "error": "Give owner/repo or a folder path."}
            return _json(self, 200, result)
        if path == "/api/plugins/remove":
            from Kerniq.plugins.distribution import remove_plugin

            result = remove_plugin(
                str((data or {}).get("name") or ""),
                confirm=True,
                plugins_dir=self._plugins_dir(),
            )
            return _json(self, 200, result)
        if path == "/api/plugins/updates":
            from Kerniq.plugins.distribution import check_updates

            return _json(self, 200, {"updates": check_updates(self._plugins_dir())})
        if path == "/api/ui/autostart":
            from Kerniq.devtools.autostart import configure
            from Kerniq.devtools.paths import find_project_root

            enabled = bool((data or {}).get("enabled"))
            return _json(self, 200, configure(enabled, project=find_project_root()))
        if path == "/api/remote/run":
            return self._remote_run(data)
        _json(self, 404, {"error": "not found"})

    def do_PUT(self) -> None:
        _identify(self)
        path, _ = _parse_qs(self.path)
        data = _read_json(self)
        if path == "/api/fs/file":
            return _json(self, 200, self._write_file(data))
        if path == "/api/ui/chats":
            return _json(self, 200, self._save_ui_chats(data))
        _json(self, 404, {"error": "not found"})

    def do_DELETE(self) -> None:
        _identify(self)
        path, qs = _parse_qs(self.path)
        if path == "/api/fs/file":
            return _json(self, 200, self._delete_file(qs.get("path", "")))
        _json(self, 404, {"error": "not found"})

    def _file(self, p: Path, ctype: str) -> None:
        if not p.exists():
            return _json(self, 404, {"error": f"missing {p.name}"})
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if getattr(self, "_kerniq_set_cookie", False) and getattr(self, "_kerniq_user", ""):
            from Kerniq.server.identity import cookie_header

            self.send_header("Set-Cookie", cookie_header(self._kerniq_user))
        self.end_headers()
        self.wfile.write(body)

    def _tools(self) -> Dict[str, Any]:
        tools = []

        def _one(t) -> Dict[str, Any]:
            return {
                "name": t.name,
                "id": t.tool_id,
                "description": t.description,
                "display_phrase": getattr(t, "display_phrase", "") or "",
            }

        if STATE.context and STATE.context.tool_registry:
            for t in STATE.context.tool_registry.list_tools():
                if getattr(t, "agent_visible", True) is False:
                    continue
                tools.append(_one(t))
        if not tools:
            try:
                from Kerniq.tools.loader import load_all_tools

                for t in load_all_tools(str(_workspace())):
                    tools.append(_one(t))
            except Exception as exc:
                logger.warning("tool pack discovery failed: %s", exc)
        return {"tools": tools}

    def _plugins(self) -> Dict[str, Any]:
        root = Path("plugins")
        plugins = []
        if root.exists():
            for d in root.iterdir():
                if d.is_dir() and (d / "manifest.toml").exists():
                    plugins.append(
                        {"id": d.name, "name": d.name, "status": "discovered"}
                    )
        return {"plugins": plugins}

    def _extensions(self) -> Dict[str, Any]:
        from Kerniq.devtools.paths import find_plugins_dirs
        from Kerniq.plugins.extensions import scan_extensions

        rows = []
        seen = set()
        for folder in find_plugins_dirs():
            for row in scan_extensions(folder):
                key = (row.get("host"), row.get("slot"), row.get("plugin_id"), row.get("id"))
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return {"extensions": rows}

    def _models(self, client: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from Kerniq.models.factory import build_provider

        ui = _settings_store().load()
        client = client or {}
        provider_id = str(client.get("provider") or ui.api.provider or "lm_studio").strip() or "lm_studio"
        ui.api.provider = provider_id
        if "base_url" in client:
            ui.api.base_url = str(client.get("base_url") or "").strip()
        if "api_token" in client:
            ui.api.api_token = str(client.get("api_token") or "")
        typed = str(ui.api.base_url or "").strip()
        urls = [typed]
        if STATE.server_mode:
            from Kerniq.server.homes import (
                LOCAL_PROVIDERS,
                hide_unused_base_url,
                local_model_candidates,
                lock_model_api,
            )

            saved = typed
            try:
                ui = hide_unused_base_url(ui)
                ui = lock_model_api(ui, _server_core())
            except PermissionError as exc:
                return {"models": [], "reachable": False, "error": str(exc), "provider": provider_id}
            if provider_id in LOCAL_PROVIDERS:
                admin = str(ui.api.base_url or "")
                stock = {
                    "http://127.0.0.1:1234",
                    "http://localhost:1234",
                    "http://127.0.0.1:11434",
                    "http://localhost:11434",
                    "http://127.0.0.1:11434/v1",
                    "http://localhost:11434/v1",
                }
                # A URL the user typed is the only address to ask.
                # The stock default still falls back to the admin URL.
                urls = [saved] if saved.rstrip("/") not in stock and saved else local_model_candidates(admin, saved)
            else:
                urls = [str(ui.api.base_url or "")]
        last = ""
        for url in urls or [""]:
            if url:
                ui.api.base_url = url
            try:
                provider = build_provider(
                    provider_id,
                    api=ui.api,
                    timeout=float(ui.agent.timeout_seconds or 60),
                )
            except Exception as exc:
                return {"models": [], "reachable": False, "error": str(exc), "provider": provider_id}
            if not hasattr(provider, "list_models"):
                return {"models": [], "reachable": True, "provider": provider_id}
            try:
                models = asyncio.run(asyncio.wait_for(provider.list_models(), 8))
                chat = [m for m in models if not _is_junk_model(m)]
                embeds = [m for m in models if _is_junk_model(m)]
                return {
                    "models": chat,
                    "embeddings": embeds,
                    "reachable": True,
                    "provider": provider_id,
                    "base_url": url or str(ui.api.base_url or ""),
                }
            except Exception as e:
                last = str(e)
                logger.info("model list failed for %s at %s: %s", provider_id, url, e)
        if STATE.server_mode and provider_id in {"lm_studio", "ollama"}:
            tried = urls[0] if urls else "http://127.0.0.1:1234"
            return {
                "models": [],
                "embeddings": [],
                "reachable": False,
                "provider": provider_id,
                "error": (
                    f"This server cannot reach the local model at {tried}. "
                    "Start LM Studio on the server machine. It must listen on that address, "
                    "usually http://127.0.0.1:1234. Another port: "
                    "kerniq server set model-url http://127.0.0.1:PORT"
                ),
                "detail": last,
            }
        return {"models": [], "embeddings": [], "reachable": False, "error": last or "unreachable", "provider": provider_id}

    def _tree(self, fresh: bool = False) -> Dict[str, Any]:
        try:
            ws = _workspace()
            key = str(ws)
            if not fresh:
                with _TREE_LOCK:
                    hit = _TREE_CACHE.get("tree")
                    if hit and hit["ws"] == key and time.monotonic() - hit["at"] < hit["ttl"]:
                        return hit["data"]
            started = time.monotonic()
            entries = []

            def walk(dir_path: Path, prefix: str, depth: int) -> None:
                if depth > 32:
                    return
                try:
                    kids = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                except OSError:
                    return
                for p in kids:
                    name = p.name
                    rel = f"{prefix}/{name}" if prefix else name
                    rel = rel.replace(chr(92), "/")
                    hidden = name.startswith(".")
                    try:
                        is_dir = p.is_dir()
                    except OSError:
                        continue
                    if is_dir:
                        entries.append({"path": rel, "type": "dir", "name": name, "hidden": hidden})
                        if not p.is_symlink():  # a linked folder is listed but not entered: no loops
                            walk(p, rel, depth + 1)
                    else:
                        entries.append({"path": rel, "type": "file", "name": name, "hidden": hidden})

            walk(ws, "", 0)
            shown = _workspace_label(ws)
            data = {"entries": entries, "workspace": shown}
            cost = time.monotonic() - started
            with _TREE_LOCK:
                _TREE_CACHE["tree"] = {"ws": key, "at": time.monotonic(), "ttl": min(30.0, cost * 10.0), "data": data}
            return data
        except Exception as e:
            return {"error": str(e), "entries": []}


    def _read_file(self, rel: str) -> Dict[str, Any]:
        try:
            path = _safe(_workspace(), rel)
            return {
                "path": rel,
                "content": path.read_text(encoding="utf-8", errors="replace"),
            }
        except Exception as e:
            return {"error": str(e)}

    def _download(self, rel: str) -> None:
        if not STATE.server_mode:
            return _json(self, 403, {"error": "Download is available in server mode."})
        from Kerniq.server.transfer import build_download

        try:
            ws = _workspace()
            target = _safe(ws, rel or ".")
            body, filename, content_type = build_download(ws, target)
        except FileNotFoundError:
            return _json(self, 404, {"error": "not found"})
        except PermissionError as exc:
            return _json(self, 403, {"error": str(exc)})
        except ValueError as exc:
            return _json(self, 413, {"error": str(exc)})
        except Exception as exc:
            return _json(self, 400, {"error": str(exc)})
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        if getattr(self, "_kerniq_set_cookie", False) and getattr(self, "_kerniq_user", ""):
            from Kerniq.server.identity import cookie_header

            self.send_header("Set-Cookie", cookie_header(self._kerniq_user))
        self.end_headers()
        self.wfile.write(body)

    def _write_file(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rel = data.get("path") or ""
            path = _safe(_workspace(), rel)
            content = data.get("content") or ""
            if STATE.server_mode:
                from Kerniq.server.homes import admit_bytes

                old = path.stat().st_size if path.is_file() and not path.is_symlink() else 0
                reason = admit_bytes(len(content.encode("utf-8")), old)
                if reason:
                    return {"error": reason}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"ok": True, "path": rel}
        except Exception as e:
            return {"error": str(e)}

    def _delete_file(self, rel: str) -> Dict[str, Any]:
        try:
            import shutil
            path = _safe(_workspace(), rel)
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            else:
                return {"error": "not found"}
            return {"ok": True, "path": rel}
        except Exception as e:
            return {"error": str(e)}

    def _create_path(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rel = (data.get("path") or "").strip().replace(chr(92), "/")
            kind = data.get("kind") or "file"
            if not rel or ".." in rel.split("/"):
                return {"error": "invalid path"}
            path = _safe(_workspace(), rel)
            if path.exists():
                return {"error": "already exists"}
            if kind == "dir":
                path.mkdir(parents=True, exist_ok=False)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data.get("content") or "", encoding="utf-8")
            return {"ok": True, "path": rel, "kind": kind}
        except Exception as e:
            return {"error": str(e)}


    def _rename(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rel = data.get("path") or ""
            new_name = (data.get("new_name") or "").strip()
            if not new_name or "/" in new_name or "\\" in new_name:
                return {"error": "invalid name"}
            ws = _workspace()
            src = _safe(ws, rel)
            dest = src.parent / new_name
            dest = _safe(ws, str(dest.relative_to(ws)))
            if dest.exists():
                return {"error": "target exists"}
            src.rename(dest)
            new_rel = str(dest.relative_to(ws)).replace(chr(92), "/")
            return {"ok": True, "path": new_rel}
        except Exception as e:
            return {"error": str(e)}

    def _reveal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        import os
        import subprocess
        if STATE.server_mode:
            return {"error": "Show in explorer is not available in server mode."}
        try:
            rel = data.get("path") or ""
            path = _safe(_workspace(), rel)
            if os.name == "nt":
                subprocess.Popen(["explorer", "/select,", str(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}


    def _plugins_dir(self) -> Path:
        here = Path(__file__).resolve()
        for parent in [Path.cwd(), *here.parents]:
            cand = parent / "plugins"
            if (cand / "web_ui" / "manifest.toml").exists():
                return cand
        return Path("plugins")

    def _discover_plugins(self, store) -> list:
        import importlib.util
        import tomllib

        from Kerniq.plugins.manager import normalize_manifest_data

        root = self._plugins_dir()
        rows = []
        if not root.is_dir():
            return rows
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and (p / "manifest.toml").exists()):
            mid = folder.name
            mname = folder.name
            status = "discovered"
            err = ""
            sch = None
            actions = []
            try:
                with open(folder / "manifest.toml", "rb") as fh:
                    data = normalize_manifest_data(tomllib.load(fh))
                mid = str(data.get("plugin_id") or folder.name)
                mname = str(data.get("name") or mid)
            except Exception as ex:
                err = str(ex)
                status = "error"
            main_py = folder / "main.py"
            if main_py.exists():
                try:
                    spec = importlib.util.spec_from_file_location(
                        "kerniq_ui_scan_" + folder.name, main_py
                    )
                    if spec is not None and spec.loader is not None:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        cls = getattr(mod, "PluginImpl", None)
                        if cls is not None:
                            inst = cls()
                            getter = getattr(inst, "settings_schema", None)
                            sch = getter() if callable(getter) else None
                            actions = []
                            try:
                                raw_actions = inst.actions() if hasattr(inst, "actions") else []
                                for action in raw_actions or []:
                                    if isinstance(action, dict) and action.get("id"):
                                        actions.append({
                                            "id": str(action.get("id")),
                                            "label": str(action.get("label") or action.get("id")),
                                            "description": str(action.get("description") or ""),
                                        })
                            except Exception:
                                logger.info("plugin actions unreadable: %s", folder.name, exc_info=True)
                            from Kerniq.plugins.fields import with_manager_fields

                            sch = with_manager_fields(sch, mid, mname)
                            status = "available"
                            try:
                                mid = inst.manifest.plugin_id or mid
                                mname = inst.manifest.name or mname
                            except Exception:
                                pass
                except Exception as ex:
                    err = str(ex)
                    if status != "available":
                        status = "error"
            if sch is None:
                from Kerniq.plugins.fields import with_manager_fields

                sch = with_manager_fields(None, mid, mname)
            item = {
                "id": (getattr(sch, "component_id", None) or mid),
                "name": (getattr(sch, "title", None) or mname),
                "status": status,
                "schema": sch.to_public() if sch else None,
                "values": {},
                "actions": actions if status == "available" else [],
            }
            if sch is not None:
                try:
                    item["values"] = store.load("plugin", sch.component_id, sch)
                except Exception:
                    item["values"] = {}
            if err:
                item["error"] = err
            from Kerniq.plugins.distribution import describe_source

            item["source"] = describe_source(folder, item["id"])
            item["version"] = ""
            try:
                import tomllib as _toml

                with open(folder / "manifest.toml", "rb") as fh:
                    _raw = _toml.load(fh)
                _block = _raw.get("plugin") if isinstance(_raw, dict) and isinstance(_raw.get("plugin"), dict) else _raw
                item["version"] = str((_block or {}).get("version") or "")
            except Exception:
                pass
            rows.append(item)
        if root.is_dir():
            from Kerniq.interfaces.settings_schema import SettingsSchema

            schemas = {}
            for row in rows:
                public = row.get("schema")
                if isinstance(public, dict):
                    try:
                        schemas[row["id"]] = SettingsSchema(**public)
                        continue
                    except Exception:
                        pass
                schemas[row["id"]] = None
            try:
                store.reconcile("plugin", schemas)
            except Exception:
                logger.exception("plugin settings reconcile")
        return rows

    def _component_store(self):
        from Kerniq.settings.component_store import ComponentSettingsStore
        from Kerniq.settings.loader import SettingsProvider
        return ComponentSettingsStore(SettingsProvider().config.storage.state_dir)

    def _list_components(self):
        """Dynamic list of tools/plugins with schemas for UI."""
        from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
        from Kerniq.tools.loader import load_all_tools
        from Kerniq.security.policy import SecurityPolicy

        tools: list = []
        plugins: list = []
        try:
            ws = _workspace()
            policy = SecurityPolicy(workspace_root=ws)
            instances = list(load_all_tools(str(ws), policy=policy))
            from Kerniq.settings.loader import SettingsProvider
            from Kerniq.tools.runtime_settings import apply_stored_tool_settings
            from Kerniq.tools.settings import ToolSettingsStore

            state_dir = SettingsProvider().config.storage.state_dir
            apply_stored_tool_settings(instances, state_dir)
            store = self._component_store()
            enabled_map = dict(ToolSettingsStore(state_dir).load().enabled_tools or {})
            for tool in instances:
                try:
                    schema = tool.settings_schema()
                    from Kerniq.tools.runtime_settings import ensure_common_fields

                    schema = ensure_common_fields(schema, tool)
                    values = store.load("tool", tool.tool_id, schema) if schema else {}
                    phrase = getattr(tool, "display_phrase", "") or ""
                    tools.append({
                        "id": tool.tool_id,
                        "name": tool.name,
                        "description": tool.description or "",
                        "category": getattr(tool, "category", "other") or "other",
                        "pack_id": getattr(tool, "pack_id", None) or getattr(tool, "category", "other"),
                        "ui_icon": getattr(tool, "ui_icon", "tool"),
                        "collapsible": bool(getattr(tool, "collapsible", False)),
                        "risk_level": getattr(tool, "risk_level", "medium"),
                        "auto_accept": bool(getattr(tool, "cfg_auto_accept", False)),
                        "include_in_plan": bool(getattr(tool, "include_in_plan", False)),
                        "display_phrase": phrase,
                        "chat_label": tool.chat_label(1) if hasattr(tool, "chat_label") else tool.name,
                        "enabled": bool(enabled_map.get(tool.tool_id, enabled_map.get(tool.name, True))),
                        "schema": schema.to_public() if schema else None,
                        "values": values or {},
                    })
                except Exception as ex:
                    logger.exception("tool component")
                    tools.append({
                        "id": getattr(tool, "tool_id", "unknown"),
                        "name": getattr(tool, "name", "?"),
                        "description": str(ex),
                        "category": "other",
                        "enabled": True,
                        "schema": None,
                        "values": {},
                    })

            # Prefer each plugin folder under plugins/. One failure must not hide the rest.
            try:
                plugins.extend(self._discover_plugins(store))
            except Exception as ex:
                logger.exception("plugin discovery")
                plugins.append({
                    "id": "discovery",
                    "name": "Plugin discovery",
                    "status": "error",
                    "schema": None,
                    "values": {},
                    "error": str(ex),
                })
            packs = _pack_rows_from(tools)
            plan_ready = _todo_plan_ready(tools)
        except Exception as e:
            logger.exception("list components")
            return {"tools": tools, "plugins": plugins, "packs": [], "plan_compose_available": False, "error": str(e)}
        return {"tools": tools, "plugins": plugins, "packs": packs, "plan_compose_available": plan_ready}

    def _get_component_settings(self, qs):
        kind = qs.get("kind", "tool")
        cid = qs.get("id", "")
        data = self._list_components()
        coll = data["tools"] if kind == "tool" else data["plugins"]
        for item in coll:
            if item["id"] == cid or item.get("name") == cid:
                return item
        return {"error": "not found"}

    def _save_component_settings(self, data):
        kind = data.get("kind", "tool")
        cid = data.get("id", "")
        values = data.get("values") or {}
        enabled = data.get("enabled", None)
        store = self._component_store()
        listing = self._list_components()
        if kind == "pack":
            return self._save_pack_settings(cid, values, enabled, listing, store)
        coll = listing["tools"] if kind == "tool" else listing["plugins"]
        schema = None
        for item in coll:
            if item["id"] == cid:
                if item.get("schema"):
                    from Kerniq.interfaces.settings_schema import SettingsSchema
                    schema = SettingsSchema(**item["schema"])
                break
        if kind == "plugin" and cid == "plugin_web_ui":
            # The browser cannot change where Kerniq listens or turn server mode on.
            locked = {"host", "port", "server_mode", "lan_access"}
            current = store.load(kind, cid, schema)
            for key in locked:
                if key in current:
                    values[key] = current[key]
        saved = store.save(kind, cid, values, schema)
        if enabled is not None and kind == "tool":
            from Kerniq.settings.loader import SettingsProvider
            from Kerniq.tools.settings import ToolSettingsStore

            toggles = ToolSettingsStore(SettingsProvider().config.storage.state_dir)
            current = toggles.load()
            et = dict(current.enabled_tools or {})
            et[cid] = bool(enabled)
            for item in listing["tools"]:
                if item["id"] == cid:
                    et[item["name"]] = bool(enabled)
            toggles.update(enabled_tools=et)
        self._lock_compose_plan()
        return {"ok": True, "values": saved}

    def _save_pack_settings(self, pack_id, values, enabled, listing, store):
        """Pack switches apply to every tool. Enabling a pack turns all of its tools on."""
        members = [
            item for item in (listing.get("tools") or [])
            if (item.get("pack_id") or item.get("category")) == pack_id
        ]
        if not members:
            return {"ok": False, "error": "unknown pack"}
        from Kerniq.interfaces.settings_schema import SettingsSchema
        from Kerniq.settings.loader import SettingsProvider
        from Kerniq.tools.settings import ToolSettingsStore

        toggles = ToolSettingsStore(SettingsProvider().config.storage.state_dir)
        current = toggles.load()
        flags = dict(current.enabled_tools or {})
        applied = {}
        for item in members:
            schema = None
            if item.get("schema"):
                schema = SettingsSchema(**item["schema"])
            merged = dict(item.get("values") or {})
            for key, value in (values or {}).items():
                if value is None:
                    continue
                merged[key] = value
            applied[item["id"]] = store.save("tool", item["id"], merged, schema)
            if enabled is not None:
                flags[item["id"]] = bool(enabled)
                flags[item["name"]] = bool(enabled)
        if enabled is not None:
            toggles.update(enabled_tools=flags)
        self._lock_compose_plan()
        return {"ok": True, "enabled": enabled, "values": applied}

    def _lock_compose_plan(self) -> None:
        if _todo_plan_ready(self._list_components().get("tools") or []):
            return
        store = _settings_store()
        current = store.load()
        if not current.chat.compose_plan:
            return
        current.chat.compose_plan = False
        store.save(current)

    def _reset_settings(self, data):
        if STATE.server_mode:
            return {"error": "Server settings are changed on the server, not from a browser."}
        store = self._component_store()
        scope = data.get("scope", "all")
        if scope == "all":
            n = store.reset_all()
            return {"ok": True, "reset_files": n}
        kind = data.get("kind", "tool")
        cid = data.get("id", "")
        listing = self._list_components()
        coll = listing["tools"] if kind == "tool" else listing["plugins"]
        schema = None
        for item in coll:
            if item["id"] == cid and item.get("schema"):
                from Kerniq.interfaces.settings_schema import SettingsSchema
                schema = SettingsSchema(**item["schema"])
                break
        values = store.reset(kind, cid, schema)
        return {"ok": True, "values": values}



    def _search_files(self, q: str) -> Dict[str, Any]:
        q = (q or "").strip().lower()
        ws = _workspace()
        hits = []
        if not q:
            return {"hits": []}
        try:
            for p in ws.rglob("*"):
                if not p.is_file():
                    continue
                name = p.name.lower()
                if q in name:
                    rel = str(p.relative_to(ws)).replace(chr(92), "/")
                    hits.append({"path": rel, "name": p.name})
        except Exception as e:
            return {"hits": [], "error": str(e)}
        return {"hits": hits}

    def _import_attachment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Copy an external file into workspace/attachments (sandbox)."""
        import re
        src = (data.get("source") or "").strip()
        name = (data.get("name") or "").strip()
        content_b64 = data.get("content_base64")
        suffix = Path(name or src).suffix.lower().lstrip(".")
        if suffix in _BLOCKED_ATTACH:
            return {"error": "This file type cannot be attached."}
        ws = _workspace()
        att = ws / "attachments"
        att.mkdir(parents=True, exist_ok=True)
        try:
            if content_b64:
                import base64
                raw = base64.b64decode(content_b64)
                if len(raw) > 8_000_000:
                    return {"error": "attachment is larger than 8 MB"}
                relative = str(data.get("relative") or "").replace("\\", "/").strip().lstrip("/")
                parts = [part for part in relative.split("/") if part and part not in {".", ".."}]
                if not parts:
                    parts = [re.sub(r"[^\w.\-]+", "_", name or "upload.bin")[:120] or "upload.bin"]
                else:
                    parts = [re.sub(r"[^\w.\-]+", "_", part)[:80] or "file" for part in parts]
                dest = att.joinpath(*parts)
                try:
                    if not dest.resolve().is_relative_to(att.resolve()):
                        return {"error": "attachment path leaves the workspace"}
                except OSError:
                    return {"error": "attachment path is not valid"}
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    stem = dest.stem
                    suffix = dest.suffix
                    i = 1
                    while dest.exists():
                        dest = dest.parent / f"{stem}_{i}{suffix}"
                        i += 1
                dest.write_bytes(raw)
                rel = str(dest.relative_to(ws)).replace(chr(92), "/")
                folder = ""
                if len(parts) > 1:
                    folder = str((att / parts[0]).relative_to(ws)).replace(chr(92), "/")
                return {
                    "ok": True,
                    "path": rel,
                    "folder": folder,
                    "directory": bool(folder),
                    "workspace_relative": True,
                }
            if not src:
                return {"error": "source or content required"}
            import shutil
            sp = Path(src)
            if not sp.is_file():
                return {"error": "source not a file"}
            try:
                rel_ws = sp.resolve().relative_to(ws.resolve())
                return {"ok": True, "path": str(rel_ws).replace(chr(92), "/"), "workspace_relative": True}
            except ValueError:
                pass
            if not _granted(str(sp)):
                return {"error": "That path was not chosen in the file dialog."}
            safe_name = re.sub(r"[^\w.\-]+", "_", name or sp.name)[:120]
            dest = att / safe_name
            i = 1
            while dest.exists():
                dest = att / f"{Path(safe_name).stem}_{i}{Path(safe_name).suffix}"
                i += 1
            shutil.copy2(sp, dest)
            rel = str(dest.relative_to(ws)).replace(chr(92), "/")
            return {"ok": True, "path": rel, "workspace_relative": True, "imported": True}
        except Exception as e:
            return {"error": str(e)}

    def _server_info(self) -> Dict[str, Any]:
        from Kerniq.server.firewall import lan_ipv4s

        server_mode = bool(getattr(STATE, "server_mode", False))
        ips = lan_ipv4s()
        lan = ips[0] if ips else _detect_lan_ip()
        bind = getattr(STATE, "host", "127.0.0.1")
        port = int(getattr(STATE, "port", 8765))
        public = bind not in ("127.0.0.1", "localhost", "::1")
        urls = [f"http://{ip}:{port}" for ip in ips] if (server_mode or public or bind in ("0.0.0.0", "::")) else [f"http://{bind}:{port}"]
        unlocked = False
        real = ""
        if server_mode:
            from Kerniq.server.debug import request_unlocked

            unlocked = bool(request_unlocked(self.headers, _state_dir()))
            if unlocked:
                try:
                    home = _workspace()
                    real = str((home / "workspace").resolve())
                except Exception:
                    real = ""
        return {
            "server_mode": server_mode,
            "bind_host": bind,
            "port": port,
            "lan_ip": lan,
            "urls": urls,
            "public_url": urls[0] if urls else f"http://127.0.0.1:{port}",
            "local_url": f"http://127.0.0.1:{port}",
            "firewall_note": str(getattr(STATE, "firewall_note", "") or ""),
            "folder_picker": "upload" if server_mode else "native",
            "storage_warning": self._storage_warning() if server_mode else "",
            "workspace_display": real if unlocked else "",
            "workspace_real": real if unlocked else "",
            "debug_unlocked": unlocked,
            "debug_armed": bool(_server_core().get("debug_enabled")) if server_mode else False,
            "model_base_url": str(_server_core().get("model_base_url") or "http://127.0.0.1:1234") if server_mode else "",
            "disk": self._disk_status() if server_mode else None,
            "queue": len(STATE.pending),
            "proxy_note": (
                "If the browser uses a proxy such as 127.0.0.1:10809, add this server's address "
                "to the proxy bypass list. The request never reaches Kerniq, even when a port test succeeds."
                if server_mode or bind in ("0.0.0.0", "::")
                else ""
            ),
        }

    def _disk_status(self) -> Dict[str, Any]:
        from Kerniq.server.homes import disk_note, quota_bytes, quota_status

        try:
            folder = _workspace()
            status = quota_status(folder, quota_bytes(_server_core()))
        except Exception:
            logger.info("disk status failed", exc_info=True)
            return {}
        note = disk_note(status)
        return {
            "used": status["used"],
            "limit": status["limit"],
            "near": bool(status["near"]),
            "full": bool(status["full"]),
            "message": note,
        }

    def _save_database(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"error": "The database is configured on the server: kerniq server db --user USER --password PASS"}

    def _native_dialog(self, kind: str):
        """Folder and file dialogs only exist on a local desktop with tkinter.

        A missing tkinter is normal on a server. Do not log a traceback and do
        not ask pip to install it. tkinter is part of Python, not a package.
        """
        if STATE.server_mode:
            return {
                "error": (
                    "In server mode each user stays in /workspace. "
                    "The server cannot open a folder on another computer."
                )
            }
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ModuleNotFoundError:
            logger.info("folder dialog unavailable: tkinter is not installed")
            return {"error": "Folder dialog is unavailable on this machine. Type the workspace path instead."}
        try:
            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                logger.info("folder dialog could not stay on top")
            if kind == "files":
                paths = filedialog.askopenfilenames(
                    title="Attach files",
                    filetypes=[
                        ("Documents and code", "*.md *.txt *.py *.js *.ts *.tsx *.jsx *.json *.toml *.yml *.yaml *.html *.css *.rs *.go *.java *.c *.cpp *.h *.cs *.rb *.php *.sh *.sql *.xml *.csv *.vue *.svelte"),
                        ("All files", "*.*"),
                    ],
                )
                root.destroy()
                return {"paths": list(paths or [])}
            title = "Attach folder" if kind == "attach" else "Select workspace"
            path = filedialog.askdirectory(title=title)
            root.destroy()
            if not path:
                return {"cancelled": True}
            return {"path": path}
        except Exception as e:
            logger.info("folder dialog failed: %s", e)
            return {"error": f"Folder dialog unavailable: {e}"}

    def _pick_attach_folder(self) -> Dict[str, Any]:
        """Grant one directory chosen on this machine. Server mode uploads instead."""
        picked = self._native_dialog("attach")
        if picked.get("error") or picked.get("cancelled") or not picked.get("path"):
            return picked
        chosen = Path(picked["path"])
        if _forbidden_grant(chosen):
            return {"error": "That folder is too broad to attach."}
        if not chosen.is_dir():
            return {"error": "That path is not a folder."}
        _grant_path(str(chosen))
        return {"path": str(chosen.resolve()), "external": True, "directory": True}

    def _pick_folder(self) -> Dict[str, Any]:
        """Native folder dialog via tkinter (local desktop)."""
        return self._native_dialog("workspace")

    def _pick_files(self) -> Dict[str, Any]:
        picked = self._native_dialog("files")
        if picked.get("error") or picked.get("cancelled"):
            return picked
        paths = picked.get("paths") or []
        if not paths:
            return {"cancelled": True}
        allowed = []
        blocked = []
        for raw in paths:
            suffix = Path(raw).suffix.lower().lstrip(".")
            if suffix in _BLOCKED_ATTACH:
                blocked.append(Path(raw).name)
                continue
            allowed.append(raw)
            _grant_path(raw)
        return {"paths": allowed, "blocked": blocked}


    def _lms_provider(self):
        from Kerniq.models.providers.lm_studio import LMStudioProvider
        ui = _settings_store().load()
        if STATE.server_mode:
            from Kerniq.server.homes import hide_unused_base_url, lock_model_api

            try:
                ui = hide_unused_base_url(ui)
                ui = lock_model_api(ui, _server_core())
            except PermissionError:
                logger.info("browser model URL was refused in server mode")
        return LMStudioProvider(
            base_url=ui.api.base_url,
            api_key=ui.api.api_token or None,
            model=ui.api.model or None,
            timeout=float(ui.agent.timeout_seconds or 600),
        )

    def _lms_loaded(self):
        ui = _settings_store().load()
        if (ui.api.provider or "lm_studio") != "lm_studio":
            selected = (ui.api.model or "").strip()
            return {
                "loaded": ([{"model": selected}] if selected else []),
                "selected_model": selected,
                "conflict": False,
                "selected_loaded": bool(selected),
                "provider": ui.api.provider,
                "busy": False,
            }
        try:
            loaded = asyncio.run(self._lms_provider().loaded_instances())
            ui = _settings_store().load()
            selected = (ui.api.model or "").strip()
            from Kerniq.models.identity import instance_model_key, same_model

            selected_loaded = bool(
                selected
                and any(
                    same_model(
                        instance_model_key(str(x.get("model") or x.get("id") or "")),
                        instance_model_key(selected),
                    )
                    for x in loaded
                )
            )
            return {
                "loaded": loaded,
                "selected_model": selected,
                "conflict": bool(loaded and selected and not selected_loaded),
                "selected_loaded": selected_loaded,
                "busy": self._runtime_busy(),
            }
        except Exception as e:
            return {"loaded": [], "error": str(e), "selected_model": "", "conflict": False, "selected_loaded": False, "busy": False}

    def _runtime_busy(self) -> bool:
        with STATE.runs_lock:
            return any(
                not run.get("done") and not run.get("queued")
                for run in STATE.runs.values()
            )

    def _storage_warning(self) -> str:
        if not STATE.server_mode:
            return ""
        try:
            return str(_history_store().warning or "")
        except Exception:
            logger.exception("history store")
            from Kerniq.server.settings import JSON_STORAGE_WARNING

            return JSON_STORAGE_WARNING

    def _ui_chats_path(self) -> Path:
        return _state_dir() / "ui_chats.json"

    def _load_ui_chats(self) -> Dict[str, Any]:
        user_id = getattr(self, "_kerniq_user", "local") or "local"
        warning = self._storage_warning()
        if STATE.server_mode:
            try:
                chats = _history_store().list_chats(user_id)
            except Exception:
                logger.exception("server chats")
                chats = []
            return {"chats": chats if isinstance(chats, list) else [], "storage_warning": warning}
        path = self._ui_chats_path()
        if not path.is_file():
            return {"chats": [], "storage_warning": warning}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            logger.info("ui chats unreadable", exc_info=True)
            return {"chats": [], "storage_warning": warning}
        chats = data.get("chats") if isinstance(data, dict) else data
        return {"chats": chats if isinstance(chats, list) else [], "storage_warning": warning}

    def _save_ui_chats(self, data) -> Dict[str, Any]:
        chats = (data or {}).get("chats") if isinstance(data, dict) else None
        if not isinstance(chats, list):
            return {"error": "chats must be a list"}
        user_id = getattr(self, "_kerniq_user", "local") or "local"
        warning = self._storage_warning()
        if STATE.server_mode:
            try:
                _history_store().save_chats(user_id, chats[-40:])
            except Exception:
                logger.exception("server chats save")
                return {"error": "chats were not saved", "storage_warning": warning}
            return {"ok": True, "count": len(chats[-40:]), "storage_warning": warning}
        path = self._ui_chats_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"chats": chats[-40:]}, ensure_ascii=False)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(path)
        return {"ok": True, "count": len(chats[-40:]), "storage_warning": warning}

    def _load_plan(self, model: str) -> Dict[str, Any]:
        from Kerniq.models.identity import instance_model_key
        from Kerniq.models.load_policy import plan_model_load

        info = self._lms_loaded()
        selected = instance_model_key(model or info.get("selected_model") or "")
        loaded_ids = [
            instance_model_key(str(item.get("model") or item.get("id") or ""))
            for item in (info.get("loaded") or [])
            if isinstance(item, dict)
        ]
        plan = plan_model_load(selected, [item for item in loaded_ids if item], busy=bool(info.get("busy")))
        body = plan.to_dict()
        if STATE.server_mode:
            body["choices"] = [
                item for item in (body.get("choices") or []) if item.get("id") != "unload"
            ]
            body["server_queue"] = True
            body["prompt"] = (
                "Server mode keeps loaded models. New work waits until the working model finishes."
            )
        if info.get("error"):
            body["error"] = info["error"]
        return body

    def _chat_title(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Name a chat with the model that is already loaded.

        Does not load, unload, or park anything. If no chat model is loaded,
        the title falls back to the first words of the message.
        """
        text = str((data or {}).get("text") or "").strip()
        fallback = _heuristic_title(text)
        try:
            return asyncio.run(self._chat_title_async(text, fallback))
        except Exception as exc:
            logger.info("chat title failed: %s", exc)
            return {"title": fallback, "source": "heuristic", "error": str(exc)}

    async def _chat_title_async(self, text: str, fallback: str) -> Dict[str, Any]:
        """Ask the model that is already loaded. Do not load or unload anything.

        LM Studio runs a chat completion on the loaded LLM even when the
        request names an embedding model, so parking the chat model only
        duplicated it and threw the real title away.
        """
        from Kerniq.models.identity import instance_model_key

        provider = self._lms_provider()
        try:
            loaded = await provider.loaded_instances()
        except Exception as exc:
            return {"title": fallback, "source": "heuristic", "error": str(exc)}
        model_id = ""
        for item in loaded or []:
            mid = instance_model_key(str(item.get("model") or item.get("id") or ""))
            if not mid or _is_junk_model({"id": mid}):
                continue
            model_id = mid
            break
        if not model_id:
            return {"title": fallback, "source": "heuristic", "reason": "no-loaded-model"}
        title, answered = await _title_from_loaded_model(provider, model_id, text)
        if title:
            return {"title": title, "source": "model", "model": answered or model_id}
        return {"title": fallback, "source": "heuristic", "model": model_id, "answered": answered}

    def _lms_load(self, data):
        """Load one model. ``choice`` comes from the core load plan.

        ``alongside`` loads next to whatever is already in memory.
        ``unload`` drops only idle foreign models, then loads the selected one.
        A busy foreign model is never unloaded.
        """
        try:
            from Kerniq.models.identity import instance_model_key, same_model
            from Kerniq.models.load_policy import plan_model_load

            model = instance_model_key(str((data or {}).get("model") or _settings_store().load().api.model or ""))
            if not model:
                return {"error": "no model"}
            choice = str((data or {}).get("choice") or "").strip()
            if (data or {}).get("alongside") and not choice:
                choice = "alongside"
            from Kerniq.server.queue import UNLOAD_REFUSED, unload_allowed

            if not unload_allowed(bool(STATE.server_mode), choice):
                return {"ok": False, "error": UNLOAD_REFUSED, "queued": True}
            info = self._lms_loaded()
            loaded_ids = []
            for item in (info.get("loaded") or []):
                if not isinstance(item, dict):
                    continue
                mid = instance_model_key(str(item.get("model") or item.get("id") or ""))
                if mid and mid not in loaded_ids:
                    loaded_ids.append(mid)
            plan = plan_model_load(model, loaded_ids, busy=bool(info.get("busy")))
            manual = {item.id for item in plan.choices}
            automatic = {"alongside", "unload", "unload_busy", "notify", "cancel"}
            if plan.status == "foreign" and choice not in manual and choice not in automatic:
                return {"needs_choice": True, "plan": plan.to_dict()}
            if choice == "cancel" or choice == "notify":
                return {"ok": False, "cancelled": True, "plan": plan.to_dict()}
            p = self._lms_provider()
            # unload: idle only. unload_busy: the user explicitly asked to drop a working model.
            if choice == "unload" and not plan.busy:
                for mid in loaded_ids:
                    if not same_model(mid, model):
                        asyncio.run(p.unload_model_instances(mid))
            elif choice == "unload_busy":
                for mid in loaded_ids:
                    if not same_model(mid, model):
                        asyncio.run(p.unload_model_instances(mid))
            res = asyncio.run(p.load_model(model))
            return {"ok": True, "result": res, "plan": plan.to_dict()}
        except Exception as e:
            return {"error": str(e)}

    def _plugin_impl(self, plugin_id: str):
        import importlib.util

        root = self._plugins_dir()
        if not root.is_dir():
            return None
        for folder in root.iterdir():
            main_py = folder / "main.py"
            if not folder.is_dir() or not main_py.exists():
                continue
            spec = importlib.util.spec_from_file_location("kerniq_action_" + folder.name, main_py)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "PluginImpl", None)
            if cls is None:
                continue
            inst = cls()
            found = str(getattr(getattr(inst, "manifest", None), "plugin_id", "") or folder.name)
            if found == plugin_id or folder.name == plugin_id:
                return inst
        return None

    def _start_plugin_action(self, data) -> Dict[str, Any]:
        plugin_id = str((data or {}).get("plugin_id") or "").strip()
        action_id = str((data or {}).get("action_id") or "").strip()
        if not plugin_id or not action_id:
            return {"error": "plugin_id and action_id are required"}
        if self._runtime_busy():
            return {"error": "An agent run is active. Wait for it to finish."}
        if plugin_id == "llm-benchmark" and self._benchmark_busy():
            return {"error": "A benchmark is already running. It keeps going if you leave this screen."}
        job_id = str(uuid.uuid4())
        job = {"id": job_id, "plugin_id": plugin_id, "action_id": action_id, "status": "running", "result": None, "error": ""}
        with STATE.jobs_lock:
            STATE.jobs[job_id] = job

        def _work():
            try:
                inst = self._plugin_impl(plugin_id)
                if inst is None:
                    raise ValueError("Plugin not found")
                store = self._component_store()
                schema = inst.settings_schema() if hasattr(inst, "settings_schema") else None
                values = store.load("plugin", plugin_id, schema) if schema is not None else {}
                if hasattr(inst, "apply_settings"):
                    inst.apply_settings(values or {})
                try:
                    from Kerniq.plugins.base import PluginContext
                    from Kerniq.settings.loader import SettingsProvider

                    inst._context = PluginContext(
                        logger=logger,
                        config=SettingsProvider().config,
                        event_bus=None,
                        tool_registry=None,
                    )
                except Exception:
                    logger.exception("plugin context was not attached")
                context = {
                    "workspace": str(_workspace()),
                    "client_settings": (data or {}).get("client_settings") if isinstance((data or {}).get("client_settings"), dict) else None,
                }
                result = asyncio.run(inst.run_action(action_id, context))
                job["result"] = result
                job["status"] = "done"
            except Exception as exc:
                logger.exception("plugin action failed")
                job["error"] = str(exc)
                job["status"] = "failed"

        threading.Thread(target=_work, daemon=False, name="kerniq-plugin-" + plugin_id).start()
        return {"ok": True, "job_id": job_id, "status": "running"}

    def _plugin_job(self, job_id: str) -> Dict[str, Any]:
        with STATE.jobs_lock:
            job = STATE.jobs.get(str(job_id or ""))
            if job is None:
                return {"error": "job not found"}
            return dict(job)

    def _benchmark_busy(self) -> bool:
        with STATE.jobs_lock:
            for job in STATE.jobs.values():
                if job.get("plugin_id") == "llm-benchmark" and job.get("status") == "running":
                    return True
        active = self._benchmark_active()
        return str(active.get("status") or "") == "running"

    def _benchmark_active(self) -> Dict[str, Any]:
        path = _workspace() / "benchmarks" / "active.json"
        if not path.is_file():
            return {"status": "idle"}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"status": "idle"}
        if not isinstance(data, dict):
            return {"status": "idle"}
        if str(data.get("status") or "") == "running":
            if not _pid_alive(int(data.get("pid") or 0)):
                data = dict(data)
                data["status"] = "failed"
                data["error"] = data.get("error") or "The benchmark process is gone."
        return data

    def _shutdown_server(self):
        """Close the UI socket. A running task stays in this process."""
        import threading

        def _stop():
            import time
            time.sleep(0.4)
            active = 0
            try:
                with STATE.runs_lock:
                    active = sum(1 for run in STATE.runs.values() if not run.get("done"))
            except Exception:
                active = 0
            try:
                with STATE.jobs_lock:
                    active += sum(1 for job in STATE.jobs.values() if job.get("status") == "running")
            except Exception:
                pass
            try:
                srv = STATE.server
                if srv is not None and hasattr(srv, "shutdown"):
                    srv.shutdown()
                    STATE.server = None
            except Exception:
                pass
            if active:
                print("Web UI closed. Kerniq is still working on the current task. Ctrl+C stops the process.", flush=True)
            else:
                print("Web UI closed. Kerniq is still running. Ctrl+C stops the process.", flush=True)

        threading.Thread(target=_stop, daemon=True).start()
        return {"ok": True, "message": "ui closed"}

    def _lms_unload_all(self):
        if STATE.server_mode:
            from Kerniq.server.queue import UNLOAD_REFUSED

            return {"ok": False, "error": UNLOAD_REFUSED}
        try:
            res = asyncio.run(self._lms_provider().unload_all())
            return {"ok": True, "result": res}
        except Exception as e:
            return {"error": str(e)}

    def _cancel_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str((data or {}).get("run_id") or "")
        chat_id = str((data or {}).get("chat_id") or "")
        with STATE.runs_lock:
            if not run_id:
                for rid, candidate in reversed(list(STATE.runs.items())):
                    if candidate.get("done"):
                        continue
                    if chat_id and candidate.get("chat_id") != chat_id:
                        continue
                    run_id = rid
                    break
            run = STATE.runs.get(run_id) if run_id else None
            live = run is not None and not run.get("done")
            if live and run.get("queued"):
                STATE.pending[:] = [item for item in STATE.pending if item[0] != run_id]
                run["queued"] = False
                run["done"] = True
                run["cancelled"] = True
                event = {"type": "status", "status": "cancelled", "text": "Stopped"}
                run.setdefault("log", []).append(event)
                run.setdefault("events", []).append(event)
                return {"ok": True, "run_id": run_id, "chat_id": chat_id, "queued": False}
            if live:
                run["cancelled"] = True
                # A live run is flagged directly. Do not arm the next message.
                STATE.cancel_chats.discard(str(run.get("chat_id") or chat_id))
                # Poll reads `log`. Writing only `events` left the UI on Stopping forever.
                event = {"type": "status", "status": "cancelled", "text": "Stopping…"}
                run.setdefault("log", []).append(event)
                run.setdefault("events", []).append(event)
            elif chat_id:
                # Stop arrived before this run was registered. One shot only.
                STATE.cancel_chats.add(chat_id)
            elif run is None:
                return {"ok": False, "error": "run not found"}
        try:
            broker = STATE.approvals
            if broker is not None:
                for item in broker.list_pending():
                    rid = str((item or {}).get("request_id") or "")
                    if rid:
                        broker.decide(rid, "deny", "cancelled")
        except Exception:
            logger.exception("cancel approvals failed")
        return {"ok": True, "run_id": run_id, "chat_id": chat_id}

    def _start_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        payload = dict(data or {})
        chat_id = str(payload.get("chat_id") or "default")
        user_id = str(payload.get("user_id") or getattr(self, "_kerniq_user", "local") or "local")
        payload["user_id"] = user_id
        payload["chat_id"] = chat_id
        if STATE.server_mode:
            from Kerniq.server.debug import request_unlocked

            payload["debug_unlocked"] = bool(request_unlocked(self.headers, _state_dir()))
        with STATE.runs_lock:
            pre_cancelled = chat_id in STATE.cancel_chats
            if pre_cancelled:
                STATE.cancel_chats.discard(chat_id)
            busy = any(
                not run.get("done") and not run.get("queued")
                for run in STATE.runs.values()
            )
            queued = bool(STATE.server_mode and (busy or STATE.pending) and not pre_cancelled)
            if queued:
                STATE.pending.append((run_id, payload.get("task") or "", payload))
            position = len(STATE.pending) if queued else 0
            STATE.runs[run_id] = {
                "events": [],
                "log": [],
                "done": False,
                "error": None,
                "chat_id": chat_id,
                "user_id": user_id,
                "cancelled": pre_cancelled,
                "queued": queued,
            }
        try:
            _chat_log().begin(
                chat_id,
                run_id,
                payload.get("task") or "",
                payload.get("attachments") or [],
            )
        except Exception:
            logger.exception("chat log begin failed")
        if queued:
            _emit(
                run_id,
                {
                    "type": "status",
                    "status": "queued",
                    "text": "Queued until the working model finishes.",
                },
            )
            return {"run_id": run_id, "queued": True, "position": position}
        threading.Thread(
            target=_run_agent_thread,
            args=(run_id, payload.get("task") or "", payload),
            daemon=True,
        ).start()
        return {"run_id": run_id, "queued": False, "position": 0}

    def _remote_run(self, data: Dict[str, Any]):
        if not STATE.server_mode:
            return _json(self, 400, {"error": "Server mode is off."})
        if getattr(self, "_kerniq_kind", "") != "api":
            return _json(self, 401, {"error": "The API key was rejected."})
        body = dict(data or {})
        body["user_id"] = getattr(self, "_kerniq_user", "")
        if not body.get("chat_id"):
            body["chat_id"] = "console"
        return _json(self, 200, self._start_run(body))

    def _remote_events(self, qs: Dict[str, str]):
        if not STATE.server_mode:
            return _json(self, 400, {"error": "Server mode is off."})
        if getattr(self, "_kerniq_kind", "") != "api":
            return _json(self, 401, {"error": "The API key was rejected."})
        run_id = qs.get("run_id", "")
        with STATE.runs_lock:
            run = STATE.runs.get(run_id)
            owner = str((run or {}).get("user_id") or "")
        if run is not None and owner != getattr(self, "_kerniq_user", ""):
            return _json(self, 404, {"error": "run not found"})
        return _json(self, 200, self._events(run_id, qs.get("cursor", "0")))

    def _snapshot(self, chat_id: str) -> Dict[str, Any]:
        try:
            snap = _chat_log().snapshot(chat_id)
        except Exception as exc:
            return {"error": str(exc), "messages": [], "active": False, "cursor": 0}
        broker = STATE.approvals
        snap["pending_approvals"] = broker.list_pending() if broker is not None else []
        return snap

    def _events(self, run_id: str, cursor: str = "0") -> Dict[str, Any]:
        try:
            idx = max(0, int(cursor or 0))
        except ValueError:
            idx = 0
        with STATE.runs_lock:
            run = STATE.runs.get(run_id)
            if run:
                log = list(run.get("log") or [])
                finished = bool(run.get("done"))
                error = run.get("error")
            else:
                log = None
        if log is not None:
            chunk = log[idx:]
            return {
                "events": chunk,
                "done": finished,
                "error": error,
                "cursor": idx + len(chunk),
            }
        try:
            return _chat_log().events_since(run_id, idx)
        except Exception as exc:
            return {"error": str(exc), "events": [], "done": True, "cursor": idx}


def _chat_log():
    from Kerniq.persistence.chat_log import ChatLog
    from Kerniq.settings.loader import SettingsProvider

    if STATE.chat_log is None:
        from Kerniq.devtools.paths import anchored_dir

        STATE.chat_log = ChatLog(anchored_dir(SettingsProvider().config.storage.state_dir))
    return STATE.chat_log


def _emit(run_id: str, event: Dict[str, Any]) -> None:
    with STATE.runs_lock:
        run = STATE.runs.get(run_id)
        if run:
            run.setdefault("log", []).append(event)
            run.setdefault("events", []).append(event)
    try:
        _chat_log().append(run_id, event)
    except Exception:
        logger.exception("chat log append failed")


def _finish_run(run_id: str, error: Optional[str] = None) -> None:
    with STATE.runs_lock:
        run = STATE.runs.get(run_id)
        if run:
            run["done"] = True
            run["error"] = error
            chat_id = str(run.get("chat_id") or "")
            if chat_id:
                STATE.cancel_chats.discard(chat_id)
    try:
        _chat_log().finish(run_id, done=True, error=error)
    except Exception:
        logger.exception("chat log finish failed")
    _release_queue()


def _release_queue() -> None:
    if not STATE.server_mode:
        return
    nxt = None
    with STATE.runs_lock:
        busy = any(
            not run.get("done") and not run.get("queued")
            for run in STATE.runs.values()
        )
        if busy or not STATE.pending:
            return
        nxt = STATE.pending.pop(0)
        run = STATE.runs.get(nxt[0])
        if run is not None:
            run["queued"] = False
    if nxt is None:
        return
    threading.Thread(target=_run_agent_thread, args=nxt, daemon=True).start()


def _run_agent_thread(run_id: str, task: str, payload: dict | None = None) -> None:
    payload = payload or {}
    # A new thread does not inherit the request context. The run payload is the user id.
    token = _ui_user.set(str(payload.get("user_id") or _ui_user.get() or "local"))
    try:
        asyncio.run(_run_agent_async(run_id, task, payload))
    except Exception as e:
        logger.exception("run failed")
        _emit(run_id, {"type": "assistant", "content": f"Error: {e}"})
        _finish_run(run_id, str(e))
    finally:
        _ui_user.reset(token)


def _diff_counts(before: str, after: str) -> tuple[int, int]:
    b, a = before.splitlines(), after.splitlines()
    sm = SequenceMatcher(a=b, b=a)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            removed += i2 - i1
            added += j2 - j1
    return added, removed


async def _run_agent_async(run_id: str, task: str, data: dict | None = None) -> None:
    data = data or {}
    from Kerniq.core.agent import Agent
    from Kerniq.models.factory import build_provider
    from Kerniq.assembly import build_tool_registry
    from Kerniq.settings.loader import SettingsProvider

    ui = _settings_store().load()
    client_settings = data.get("client_settings") if isinstance(data.get("client_settings"), dict) else None
    if STATE.server_mode or client_settings:
        from Kerniq.settings.browser import overlay_settings

        dumped = ui.model_dump()
        if STATE.server_mode:
            dumped.setdefault("api", {})["api_token"] = ""
        ui = type(ui).model_validate(dumped)
        ui = overlay_settings(ui, client_settings)
    disk_status = None
    if STATE.server_mode:
        from Kerniq.server.homes import (
            bind_jail,
            disk_note,
            hide_unused_base_url,
            lock_model_api,
            quota_bytes,
            quota_status,
            set_quota,
            user_home,
        )

        core = _server_core()
        try:
            ui = hide_unused_base_url(ui)
            ui = lock_model_api(ui, core)
        except PermissionError as exc:
            _emit(run_id, {"type": "status", "status": "error", "text": "Provider error"})
            _emit(run_id, {"type": "assistant", "content": str(exc), "completed": False})
            _finish_run(run_id, str(exc))
            return
        user_key = str(data.get("user_id") or _ui_user.get() or "local")
        ws = user_home(_state_dir(), user_key, core)
        bind_jail(ws)
        disk_status = quota_status(ws, quota_bytes(core))
        set_quota(disk_status)
    else:
        ws = _workspace()

    _emit(run_id, {"type": "status", "status": "processing", "text": "Processing prompt…"})

    cfg = SettingsProvider().config
    if STATE.server_mode:
        ui.agent.host_freedom = False
        ui.agent.workspace = "./workspace"
        if not data.get("debug_unlocked"):
            ui.chat.developer_mode = False
            if str(getattr(ui.chat, "auto_approve_up_to", "") or "") == "all":
                ui.chat.auto_approve_up_to = "low"
    ceiling = getattr(getattr(ui, "chat", None), "auto_approve_up_to", None) or getattr(
        cfg.security, "auto_approve_up_to", "low"
    )
    reg, policy = build_tool_registry(
        ws,
        config=cfg,
        state_dir=cfg.storage.state_dir,
        auto_approve_up_to=ceiling,
        host_freedom=bool(getattr(ui.agent, "host_freedom", False)) and not STATE.server_mode,
    )

    try:
        provider = build_provider(
            ui.api.provider or "lm_studio",
            api=ui.api,
            config=cfg,
            timeout=float(ui.agent.timeout_seconds or 600),
        )
    except Exception as exc:
        _emit(run_id, {"type": "status", "status": "error", "text": "Provider error"})
        _emit(run_id, {"type": "assistant", "content": f"Provider error: {exc}", "completed": False})
        _finish_run(run_id, str(exc))
        return

    agent = Agent(provider, reg)
    agent.orchestrator.security_policy = policy
    from Kerniq.security.approval_broker import BrokerApprovalProvider

    def _on_approval(req):
        _emit(run_id, {"type": "approval", "request": req.model_dump(mode="json")})

    def _is_cancelled_early() -> bool:
        with STATE.runs_lock:
            return bool(STATE.runs.get(run_id, {}).get("cancelled"))

    agent.orchestrator.approval_provider = BrokerApprovalProvider(
        STATE.approvals,
        _on_approval,
        cancel_check=_is_cancelled_early,
    )

    def _checkpoint(ctx):
        try:
            from Kerniq.persistence.manager import SessionManager
            from Kerniq.storage.json_store import JsonStorage

            transcript = (ctx.metadata or {}).get("transcript") or [
                m.model_dump(mode="json") for m in ctx.messages
            ]
            SessionManager(JsonStorage(Path(cfg.storage.sessions_dir))).save_task_sync(
                session_id=ctx.session_id,
                task_id=ctx.task_id,
                goal=ctx.goal,
                status=str((ctx.metadata or {}).get("outcome") or "running"),
                result="",
                workspace="/workspace" if STATE.server_mode else str(ws),
                messages=transcript,
                metadata={"outcome": (ctx.metadata or {}).get("outcome")},
            )
        except Exception:
            logger.exception("session checkpoint failed")

    agent.orchestrator.on_progress = _checkpoint

    def _on_plan(items, archive=None):
        rows = [item for item in (items or []) if isinstance(item, dict)]
        open_items = [item for item in rows if item.get("status") not in ("done", "skipped", "failed")]
        _emit(run_id, {
            "type": "plan",
            "items": rows,
            "archive": list(archive or []),
            "complete": not open_items and bool(rows),
        })

    agent.orchestrator.on_plan = _on_plan

    def _on_notice(kind, text):
        _emit(run_id, {"type": "notice", "kind": kind, "text": text})

    agent.orchestrator.on_notice = _on_notice
    try:
        from Kerniq.plugins.manager import PluginManager
        from Kerniq.plugins.base import PluginContext
        from Kerniq.devtools.paths import find_plugins_dirs

        def _plugin_ctx():
            return PluginContext(
                logger=logger,
                config=cfg,
                event_bus=None,
                tool_registry=reg,
            )

        pm = PluginManager(_plugin_ctx)
        for plugin_dir in find_plugins_dirs():
            await pm.discover_and_load(plugin_dir, skip_ids=["plugin_web_ui"])
        compactor = pm.plugins.get("plugin_context_compact")
        if compactor is not None:
            agent.orchestrator.compactor = compactor
    except Exception:
        logger.exception("plugin load during chat run failed")
    if ui.agent.max_iterations is not None:
        agent.orchestrator.max_iterations = ui.agent.max_iterations
    from Kerniq.core.runtime_flow import apply_runtime
    apply_runtime(agent.orchestrator, ui)
    # Model context window for overflow protection (best-effort)
    ctx_lim = 0
    try:
        models = await provider.list_models() if hasattr(provider, "list_models") else []
        want = (ui.api.model or "").strip()
        if not want and hasattr(provider, "resolve_auto_model"):
            try:
                want = str(await provider.resolve_auto_model() or "")
            except Exception:
                want = ""
        from Kerniq.models.identity import same_model

        first_loaded = 0
        first_catalog = 0
        matched = False
        for m in models or []:
            mid = str(m.get("id") or m.get("key") or "")
            if not mid or "embed" in mid.lower() or "rerank" in mid.lower():
                continue
            lim = int(
                m.get("loaded_context_length")
                or m.get("context_length")
                or m.get("max_context_length")
                or m.get("context")
                or 0
            )
            loaded = bool(m.get("loaded_instances") or m.get("loaded_context_length"))
            if want and same_model(mid, want):
                ctx_lim = lim
                matched = True
                break
            if loaded and not first_loaded and lim:
                first_loaded = lim
            if not first_catalog and lim:
                first_catalog = lim
        if not matched:
            ctx_lim = first_loaded or first_catalog
    except Exception:
        pass
    agent.orchestrator.context_limit = int(ctx_lim or 0)
    agent.orchestrator.model_context_limit = int(ctx_lim or 0)
    agent.orchestrator.user_output_cap = ui.api.max_tokens
    from Kerniq.core.runtime_flow import clamp_output_tokens

    cap = clamp_output_tokens(ui.api.max_tokens, ctx_lim)
    agent.orchestrator.generation_options = agent.orchestrator.generation_options.model_copy(
        update={"max_tokens": cap}
    )
    compactor = getattr(agent.orchestrator, "compactor", None)
    if compactor is not None:
        compactor.cfg_context_limit = int(ctx_lim or 0)
    retries = int(getattr(ui.agent, "loop_retries", None) or 4)
    agent.orchestrator.max_content_loop_hits = max(1, retries)
    agent.orchestrator.max_identical_tool_streak = max(2, retries)
    agent.orchestrator.max_plan_continuations = max(1, retries)

    orig_generate = provider.generate

    def _is_cancelled() -> bool:
        with STATE.runs_lock:
            return bool(STATE.runs.get(run_id, {}).get("cancelled"))

    agent.orchestrator.cancel_check = _is_cancelled

    async def generate_with_status(request):
        if (request.metadata or {}).get("kerniq_internal"):
            if request.metadata is None:
                request.metadata = {}
            request.metadata["cancel_check"] = _is_cancelled
            if _is_cancelled():
                from Kerniq.interfaces.models import ModelResponse, Message, MessageRole
                return ModelResponse(
                    messages=[Message(role=MessageRole.ASSISTANT, content="")],
                    finish_reason="cancelled",
                    metadata={"cancelled": True},
                )
            response = await orig_generate(request)
            return response
        if _is_cancelled():
            from Kerniq.interfaces.models import ModelResponse, Message, MessageRole
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="")],
                finish_reason="cancelled",
                metadata={"cancelled": True},
            )
        _emit(run_id, {"type": "status", "status": "processing", "text": "Processing prompt…"})
        saw_content = {"v": False}
        saw_reason = {"v": False}
        hb_stop = {"v": False}

        async def _heartbeat():
            import asyncio as _aio
            n = 0
            while not hb_stop["v"] and not _is_cancelled():
                await _aio.sleep(15.0)
                if hb_stop["v"] or _is_cancelled():
                    break
                n += 1
                phase = (
                    "Generating…" if saw_content["v"]
                    else ("Thinking…" if saw_reason["v"] else "Processing prompt…")
                )
                _emit(run_id, {
                    "type": "heartbeat",
                    "text": f"{phase} ({n * 15}s)",
                    "seconds": n * 15,
                })

        import asyncio as _aio
        hb_task = _aio.create_task(_heartbeat())

        def on_delta(ev):
            if _is_cancelled():
                return
            if ev.get("type") == "reasoning":
                if not saw_reason["v"]:
                    saw_reason["v"] = True
                    _emit(run_id, {"type": "status", "status": "thinking", "text": "Thinking…"})
                _emit(run_id, {"type": "reasoning_delta", "text": ev.get("text") or ""})
            elif ev.get("type") == "content":
                if not saw_content["v"]:
                    saw_content["v"] = True
                    _emit(run_id, {"type": "status", "status": "generating", "text": "Generating…"})
                _emit(run_id, {"type": "content_delta", "text": ev.get("text") or ""})

        try:
            if request.metadata is None:
                request.metadata = {}
            request.metadata["on_stream_delta"] = on_delta
            request.metadata["cancel_check"] = _is_cancelled
        except Exception:
            pass
        try:
            resp = await orig_generate(request)
        except asyncio.CancelledError:
            hb_stop["v"] = True
            try:
                hb_task.cancel()
            except Exception:
                pass
            raise
        except Exception as e:
            msg = str(e)
            low = msg.lower()
            if any(x in low for x in ("not loaded", "no model", "unload", "model_not")):
                _emit(run_id, {
                    "type": "status",
                    "status": "error",
                    "text": "Model not loaded in LM Studio",
                    "detail": msg,
                })
                _emit(run_id, {
                    "type": "assistant",
                    "content": "Model not loaded in LM Studio",
                    "error": True,
                    "detail": msg,
                    "completed": False,
                })
            else:
                _emit(run_id, {"type": "status", "status": "error", "text": "Model error", "detail": msg})
                _emit(run_id, {
                    "type": "assistant",
                    "content": "Model error",
                    "error": True,
                    "detail": msg,
                    "completed": False,
                })
            hb_stop["v"] = True
            try:
                hb_task.cancel()
            except Exception:
                pass
            raise
        if getattr(resp, "finish_reason", None) == "cancelled" or (resp.metadata or {}).get("cancelled"):
            hb_stop["v"] = True
            try:
                hb_task.cancel()
            except Exception:
                pass
            return resp
        reasoning = None
        if resp.metadata:
            reasoning = resp.metadata.get("reasoning")
        if not reasoning:
            for msg in resp.messages:
                if msg.metadata and msg.metadata.get("reasoning"):
                    reasoning = msg.metadata.get("reasoning")
        if reasoning and str(reasoning).strip():
            _emit(run_id, {"type": "think_done", "text": reasoning})
        from Kerniq.core.runtime_flow import promote_reasoning
        from Kerniq.models.text_tools import adopt_channel_calls, parse_text_tool_calls

        promote_reasoning(resp)
        known = set()
        schemas = {}
        try:
            for item in (getattr(request, "tools", None) or []):
                if not isinstance(item, dict):
                    continue
                fn = item.get("function") if isinstance(item.get("function"), dict) else item
                name = str(fn.get("name") or "")
                if not name:
                    continue
                known.add(name)
                params = fn.get("parameters") or fn.get("input_schema") or {}
                props = params.get("properties") if isinstance(params, dict) else None
                if isinstance(props, dict) and props:
                    schemas[name] = list(props.keys())
        except Exception:
            known = set()
            schemas = {}
        for msg in resp.messages:
            if getattr(msg, "tool_calls", None):
                cleaned, kept = adopt_channel_calls(msg.content or "", msg.tool_calls)
                msg.content = cleaned
                msg.tool_calls = kept
                continue
            content = msg.content or ""
            cleaned, calls = adopt_channel_calls(content, None)
            if calls:
                msg.content = cleaned
                msg.tool_calls = calls
                continue
            if not known:
                continue
            cleaned, calls = parse_text_tool_calls(content, known, schemas)
            if calls:
                msg.content = cleaned
                msg.tool_calls = calls
                continue
            meta = getattr(msg, "metadata", None) or {}
            thought = str(meta.get("reasoning") or "") if isinstance(meta, dict) else ""
            if thought and not content.strip():
                _cleaned, calls = adopt_channel_calls(thought, None)
                if not calls:
                    _cleaned, calls = parse_text_tool_calls(thought, known, schemas)
                if calls:
                    msg.tool_calls = calls
        texts = [m.content for m in resp.messages if (m.content or "").strip()]
        if not texts and not any(m.tool_calls for m in resp.messages):
            _emit(run_id, {
                "type": "status",
                "status": "empty_done",
                "text": "Empty reply, retrying…",
                "detail": str(getattr(resp, "finish_reason", "") or "no content"),
            })
        tps = (resp.metadata or {}).get("tokens_per_second")
        if tps:
            _emit(run_id, {"type": "tps", "value": float(tps)})
        # Real usage from provider when available (drives footer context)
        if resp.usage:
            _emit(run_id, {
                "type": "usage",
                "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
                "completion_tokens": getattr(resp.usage, "completion_tokens", None),
                "total_tokens": getattr(resp.usage, "total_tokens", None),
            })
        # Approximate completion tokens from stream for TPS if no provider speed
        if not tps and resp.usage and getattr(resp.usage, "completion_tokens", None):
            pass
        for msg in resp.messages:
            if msg.tool_calls:
                _emit(run_id, {"type": "status", "status": "tool", "text": "Calling tool…"})
                for tc in msg.tool_calls:
                    _emit(
                        run_id,
                        {
                            "type": "tool",
                            "name": tc.name,
                            "status": "pending",
                            "summary": "",
                            "args": tc.arguments,
                        },
                    )
        hb_stop["v"] = True
        try:
            hb_task.cancel()
        except Exception:
            pass
        return resp

    provider.generate = generate_with_status

    # cancel flag polled by generate wrapper
    orig_gen2 = provider.generate
    async def generate_cancelable(request):
        with STATE.runs_lock:
            if STATE.runs.get(run_id, {}).get("cancelled"):
                from Kerniq.interfaces.models import ModelResponse, Message, MessageRole
                return ModelResponse(
                    messages=[Message(role=MessageRole.ASSISTANT, content="")],
                    finish_reason="cancelled",
                    metadata={"cancelled": True},
                )
        return await orig_gen2(request)
    provider.generate = generate_cancelable
  # type: ignore

    for tool in reg.list_tools():
        orig_exec = tool.execute
        tname = tool.name

        async def wrapped(arguments, context, _orig=orig_exec, _name=tname):
            if _is_cancelled():
                try:
                    context.cancelled = True
                except Exception:
                    pass
                from Kerniq.interfaces.tools import ToolResult
                return ToolResult(
                    tool_call_id=getattr(context, "last_tool_call_id", "unknown"),
                    tool_id=_name,
                    status="error",
                    success=False,
                    stop_reason="cancelled",
                    output="",
                    human_readable="Stopped by user.",
                    error="cancelled",
                )
            _emit(run_id, {"type": "status", "status": "tool", "text": f"Running tool: {_name}…"})
            _emit(run_id, {"type": "status", "status": "waiting_tool", "text": f"Waiting for tool: {_name}…"})
            before = None
            path = arguments.get("path")
            if _name in ("write_file", "create_file", "edit_file", "delete_file") and path:
                try:
                    fp = _safe(ws, path)
                    if fp.exists() and fp.is_file():
                        before = fp.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass
            result = await _orig(arguments, context)
            status = "success" if getattr(result, "success", result.status == "success") else "error"
            _emit(
                run_id,
                {
                    "type": "tool",
                    "name": _name,
                    "status": status,
                    "success": status == "success",
                    "stop_reason": getattr(result, "stop_reason", status),
                    "summary": (
                        ((getattr(result, "human_readable", None) or result.error or "")[:400])
                        if (getattr(result, "success", True) is False or getattr(result, "status", "") == "error")
                        else ""
                    ),
                    "args": arguments,
                },
            )
            if path and status == "success":
                if _name == "delete_file":
                    _emit(run_id, {"type": "file_op", "op": "delete", "path": path})
                elif _name == "create_file":
                    content = arguments.get("content") or ""
                    lines = content.count("\n") + (1 if content else 0)
                    _emit(
                        run_id,
                        {
                            "type": "file_op",
                            "op": "create",
                            "path": path,
                            "added": lines,
                            "removed": 0,
                        },
                    )
                elif _name in ("write_file", "edit_file"):
                    try:
                        after = _safe(ws, path).read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        after = arguments.get("content") or ""
                    added, removed = _diff_counts(before or "", after)
                    op = "create" if before is None else "edit"
                    _emit(
                        run_id,
                        {
                            "type": "file_op",
                            "op": op,
                            "path": path,
                            "added": added,
                            "removed": removed,
                        },
                    )
            return result

        tool.execute = wrapped  # type: ignore

    from Kerniq.interfaces.models import Message, MessageRole

    chat_id = str(data.get("chat_id") or "default")
    user_id = str(data.get("user_id") or "local")
    memory_id = _history_key(user_id, chat_id)
    history_msgs: list = []
    with STATE.chat_lock:
        stored = list(STATE.chat_histories.get(memory_id) or [])
    if not stored:
        try:
            stored = _chat_log().model_messages(memory_id)
        except Exception:
            logger.exception("model history load failed")
            stored = []
        if stored:
            with STATE.chat_lock:
                if not STATE.chat_histories.get(memory_id):
                    STATE.chat_histories[memory_id] = list(stored)
                else:
                    stored = list(STATE.chat_histories[memory_id])
    try:
        client_hist = data.get("history") or []
    except Exception:
        client_hist = []
        logger.exception("client history parse")
    for row in merge_histories(stored, client_hist):
        msg = history_message(row)
        if msg is not None:
            history_msgs.append(msg)

    system = (ui.prompt.system_prompt or "").strip() or None
    # File reference protocol for the UI
    file_link_hint = (
        "When referring to project files, write links as [[file:relative/path]] "
        "(workspace-relative). The UI will open them in the editor. "
        "An @path token in the user message is a workspace file mention. Read that relative path. "
        "Do not invent paths."
    )
    if system:
        system = system.rstrip() + "\n\n" + file_link_hint
    else:
        system = file_link_hint
    if STATE.server_mode:
        from Kerniq.server.homes import disk_note

        system += (
            "\n\nYour folders are ./workspace and ./attachments. "
            "Those names are not disk paths. Work only inside them. "
            "Do not try to read other users, the rest of this machine, or any path outside those folders."
        )
        note = disk_note(disk_status)
        if note:
            system += "\n\n" + note

    # Never bake system into task
    user_task = (task or "").strip()
    if user_task.startswith("[System]") or user_task.startswith("[system]"):
        # client bug — extract user part only
        import re as _re
        mm = _re.search(r"\[User\]\s*(.*)$", user_task, flags=_re.S | _re.I)
        if mm:
            user_task = mm.group(1).strip()

    prior_rows = transcript_rows(history_msgs)

    def _event_partial() -> str:
        with STATE.runs_lock:
            log = list((STATE.runs.get(run_id) or {}).get("log") or [])
        return partial_assistant_text(log)

    def _remember(context, *, cancelled=False) -> None:
        try:
            rows = compose_saved_history(
                prior_rows,
                getattr(context, "messages", None) if context is not None else None,
                user_task=user_task,
                partial=_event_partial(),
                cancelled=cancelled,
            )
            with STATE.chat_lock:
                STATE.chat_histories[memory_id] = rows
            try:
                _chat_log().save_model_messages(memory_id, rows)
            except Exception:
                logger.exception("model history persist failed")
            if STATE.server_mode:
                try:
                    _history_store().save_replies(user_id, chat_id, rows)
                except Exception:
                    logger.exception("server reply save failed")
        except Exception:
            logger.exception("history save failed")

    def _finish_cancelled() -> None:
        _remember(getattr(agent, "last_context", None), cancelled=True)
        _emit(run_id, {"type": "status", "status": "cancelled", "text": "Stopped"})
        _emit(run_id, {"type": "cleanup_think"})
        _finish_run(run_id, None)

    logger.info(
        "run chat_id=%s history=%s system_len=%s task=%r",
        chat_id, len(history_msgs), len(system or ""), user_task[:120],
    )
    lang = getattr(getattr(ui, "chat", None), "response_language", None) or "auto"
    agent.response_language = lang
    allowed_files = []
    external_files = []
    image_paths = []
    from Kerniq.models.vision import is_image_name

    for item in data.get("attachments") or []:
        raw_path = item.get("path") if isinstance(item, dict) else str(item)
        raw_path = str(raw_path or "").strip()
        if is_image_name(raw_path):
            if isinstance(item, dict) and item.get("external"):
                if _granted(raw_path):
                    image_paths.append(str(Path(raw_path).resolve()))
            else:
                rel = raw_path.replace("\\", "/").lstrip("./")
                if rel:
                    image_paths.append(str((ws / rel).resolve()))
        if STATE.server_mode and isinstance(item, dict) and item.get("external"):
            continue
        if isinstance(item, dict) and item.get("external"):
            raw = str(item.get("path") or "").strip()
            if raw and _granted(raw):
                external_files.append(str(Path(raw).resolve()))
            elif raw:
                logger.warning("Rejected external attachment that was not granted by the file dialog")
            continue
        path = item.get("path") if isinstance(item, dict) else str(item)
        path = str(path or "").replace("\\", "/").lstrip("./")
        if path:
            allowed_files.append(path)
    strict = bool(allowed_files) or bool(getattr(cfg.security, "strict_attachments", False))
    if allowed_files:
        system = (system or "") + (
            "\n\nStrict attachment mode is on. You may only read or write these workspace paths: "
            + ", ".join(allowed_files)
            + ". Other workspace paths will be denied."
        )
    read_only_external = bool(getattr(ui.chat, "read_only_external_attachments", True))
    from Kerniq.security.pathmask import alias_attachments

    attachment_map = alias_attachments(external_files)
    if attachment_map:
        names = "\n".join(attachment_map)
        if read_only_external:
            system = (system or "") + (
                "\n\nThese attached paths are ./attachments. You may read them. "
                "You may not write, edit, move, or delete them. "
                "They are not host paths:\n"
                + names
            )
        else:
            system = (system or "") + (
                "\n\nThese attached paths are ./attachments. You may read and change them. "
                "They are not host paths:\n"
                + names
            )
    mode = str(data.get("mode") or getattr(ui.chat, "agent_mode", None) or "act").lower()
    if mode not in ("plan", "act"):
        mode = "act"
    auto_act = bool(getattr(ui.chat, "auto_act_after_plan", True))
    if "auto_act" in data:
        auto_act = bool(data.get("auto_act"))
    mode_auto = bool(getattr(ui.chat, "mode_auto", True))
    if "mode_auto" in data:
        mode_auto = bool(data.get("mode_auto"))
    compose_plan = bool(getattr(ui.chat, "compose_plan", True))
    if "compose_plan" in data:
        compose_plan = bool(data.get("compose_plan"))
    from Kerniq.core.runtime_flow import compose_plan_allowed
    if not compose_plan_allowed(reg):
        compose_plan = False
        ui.chat.compose_plan = False
        if not STATE.server_mode and client_settings is None:
            try:
                _settings_store().save(ui)
            except Exception:
                logger.exception("could not turn compose_plan off")
    agent.orchestrator.compose_plan = compose_plan
    agent.orchestrator.finish_open_plan = False
    if compose_plan:
        system = (system or "") + (
            " Until a TODO exists, the first turn is update_plan and nothing else."
        )
    initial_plan = data.get("plan") if isinstance(data.get("plan"), list) else None
    initial_archive = data.get("archive") if isinstance(data.get("archive"), list) else None

    async def _use_mode_model(mode_name: str) -> None:
        from Kerniq.core.runtime_flow import probe_context_limit, use_model_for_mode

        before = str(getattr(provider, "model", "") or "")
        err = await use_model_for_mode(provider, ui.api, mode_name)
        if err:
            _emit(run_id, {
                "type": "assistant",
                "content": f"Could not switch to the {mode_name} model. Continuing with the current one.",
                "error": True,
                "detail": err,
                "completed": False,
            })
        after = str(getattr(provider, "model", "") or "")
        if after and after != before:
            _emit(run_id, {"type": "status", "status": "loading_model", "text": after})
        limit = 0
        try:
            limit = int(await probe_context_limit(provider, after) or 0)
        except Exception:
            logger.exception("context probe failed")
        if limit:
            agent.orchestrator.context_limit = limit
            compactor = getattr(agent.orchestrator, "compactor", None)
            if compactor is not None:
                compactor.cfg_context_limit = limit
        _emit(run_id, {
            "type": "model",
            "mode": mode_name,
            "model": after,
            "context_limit": limit,
        })

    async def _verdict(task_text: str) -> str:
        from Kerniq.core.runtime_flow import route_mode
        return await route_mode(provider, task_text, compose_plan=compose_plan)

    async def _await_cancel(coro):
        """Stop must unblock routing and model load, not only the agent loop."""
        task = asyncio.create_task(coro)
        try:
            while not task.done():
                if _is_cancelled():
                    task.cancel()
                    try:
                        await asyncio.wait_for(task, 1.5)
                    except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                        pass
                    return None
                await asyncio.sleep(0.2)
            return task.result()
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
            raise

    if mode_auto:
        routed = await _await_cancel(_verdict(user_task))
        if _is_cancelled():
            _finish_cancelled()
            return
        if isinstance(routed, str) and routed:
            mode = routed
    if _is_cancelled():
        _finish_cancelled()
        return
    _emit(run_id, {"type": "mode", "mode": mode})
    await _await_cancel(_use_mode_model(mode))
    if _is_cancelled():
        _finish_cancelled()
        return

    async def _one(task_text, hist, run_mode, plan0, archive0=None, system_text=None, plan_gate=True, pictures=None):
        return await agent.run(
            task_text,
            workspace=str(ws),
            system_prompt=system if system_text is None else system_text,
            history=hist,
            response_language=lang,
            allowed_files=allowed_files or None,
            strict_attachments=strict,
            agent_mode=run_mode,
            initial_plan=plan0,
            plan_archive=archive0,
            plan_handoff=bool(run_mode == "plan" and auto_act and compose_plan),
            plan_gate=plan_gate,
            external_files=external_files or None,
            external_read_only=read_only_external,
            image_paths=pictures or None,
            attachment_aliases=attachment_map or None,
        )

    if _is_cancelled():
        _finish_cancelled()
        return

    try:
        result = await _one(user_task, history_msgs or None, mode, initial_plan, initial_archive, None, True, image_paths)
    except Exception as e:
        if _is_cancelled():
            _finish_cancelled()
        else:
            title, detail = _public_error(e)
            _emit(run_id, {"type": "status", "status": "error", "text": title, "detail": detail})
            _emit(run_id, {
                "type": "assistant",
                "content": title,
                "error": True,
                "detail": detail,
                "completed": False,
            })
            _finish_run(run_id, str(e))
        return

    if _is_cancelled():
        _finish_cancelled()
        return

    def _outcome():
        if agent.last_context is None:
            return ""
        return str((agent.last_context.metadata or {}).get("outcome") or "")

    def _plan_items():
        if agent.last_context is None:
            return []
        raw = (agent.last_context.metadata or {}).get("plan") or []
        return list(raw) if isinstance(raw, list) else []

    plan_items = _plan_items()
    if plan_items or (agent.last_context and (agent.last_context.metadata or {}).get("plan_archive")):
        _emit(run_id, {
            "type": "plan",
            "items": plan_items,
            "archive": list((agent.last_context.metadata or {}).get("plan_archive") or []) if agent.last_context else [],
        })
    outcome = _outcome()
    if isinstance(result, str) and "TASK_COMPLETED" in result:
        result = result.replace("TASK_COMPLETED", "").rstrip()
    fail_outcomes = {
        "provider_error",
        "verification_failed",
        "tool_loop",
        "content_loop",
        "empty_response",
        "no_plan",
        "max_iterations",
    }
    failed = outcome in fail_outcomes
    open_items = [
        item for item in plan_items
        if isinstance(item, dict) and item.get("status") not in ("done", "skipped", "failed")
    ]
    handoff = (
        mode == "plan"
        and auto_act
        and not failed
        and not open_items
        and not _is_cancelled()
    )
    if mode == "plan" and not auto_act and isinstance(result, str):
        result = _strip_draft(result)
    if handoff:
        from Kerniq.core.runtime_flow import act_followup_task, handoff_archive, plan_research_record
        research = handoff_archive(agent.last_context)
        _emit(run_id, {"type": "plan", "items": [], "archive": research})
        _emit(run_id, {"type": "mode", "mode": "act"})
        _emit(run_id, {"type": "status", "status": "processing", "text": "Act", "iterations_reset": True})
        draft = plan_research_record(
            agent.last_context.messages if agent.last_context is not None else [],
            result if isinstance(result, str) else "",
        )
        await _await_cancel(_use_mode_model("act"))
        if _is_cancelled():
            _finish_cancelled()
            return
        logger.info(
            "Act starts with a fresh iteration budget (%s). Plan iterations are not carried over.",
            agent.orchestrator.max_iterations,
        )
        act_task = act_followup_task(
            user_task,
            draft,
            max_iterations=agent.orchestrator.max_iterations,
        )
        plan_hist = []
        if agent.last_context is not None:
            for row in transcript_rows(agent.last_context.messages):
                msg = history_message(row)
                if msg is not None:
                    plan_hist.append(msg)
        act_system = ((system or "") + "\n\n" + act_task).strip()
        try:
            act_result = await _one(
                user_task,
                plan_hist or None,
                "act",
                None,
                research or None,
                act_system,
                False,
            )
        except Exception as e:
            if _is_cancelled():
                _finish_cancelled()
                return
            title, detail = _public_error(e)
            _emit(run_id, {"type": "assistant", "content": title, "error": True, "detail": detail, "completed": False})
            _finish_run(run_id, str(e))
            return
        if _is_cancelled():
            _finish_cancelled()
            return
        plan_items = _plan_items() or []
        archive_now = list((agent.last_context.metadata or {}).get("plan_archive") or []) if agent.last_context else []
        if plan_items or archive_now:
            _emit(run_id, {
                "type": "plan",
                "items": plan_items,
                "archive": archive_now,
            })
        outcome = _outcome()
        if isinstance(act_result, str) and "TASK_COMPLETED" in act_result:
            act_result = act_result.replace("TASK_COMPLETED", "").rstrip()
        result = act_result
        failed = outcome in fail_outcomes
    _remember(getattr(agent, "last_context", None), cancelled=False)
    final_status = "error" if failed else "done"
    still_open = [
        item for item in (_plan_items() or plan_items)
        if isinstance(item, dict) and item.get("status") not in ("done", "skipped", "failed")
    ]
    completed = (not failed) and not still_open
    _emit(run_id, {
        "type": "assistant",
        "content": result or "",
        "completed": completed,
        "error": bool(failed),
        "detail": outcome if failed else "",
    })
    _emit(
        run_id,
        {
            "type": "status",
            "status": final_status,
            "text": outcome or ("Error" if failed else "Done"),
            "detail": outcome if failed else "",
            "completed": not failed,
        },
    )
    _emit(run_id, {"type": "cleanup_think"})
    _finish_run(run_id, outcome if failed else None)


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="plugin_web_ui",
            name="Web UI",
            version="0.2.0",
            api_version="1.0",
            entry_point="main.PluginImpl",
            description="Cursor-like local UI",
            capabilities=["ui", "http"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def extension_slots(self) -> list:
        return ["settings", "panel"]

    def settings_schema(self):
        return SettingsSchema(
            component_id="plugin_web_ui",
            component_type="plugin",
            title="Web UI",
            fields=[
                SettingField(
                    key="host",
                    label="Bind host",
                    type=SettingType.STRING,
                    default="127.0.0.1",
                    server_default="0.0.0.0",
                    description="127.0.0.1 = only this computer; 0.0.0.0 = every interface. Applied when Kerniq starts.",
                ),
                SettingField(
                    key="port",
                    label="Port",
                    type=SettingType.INT,
                    default=8765,
                    minimum=1,
                    maximum=65535,
                ),
                SettingField(
                    key="server_mode",
                    label="Server mode",
                    type=SettingType.BOOL,
                    default=False,
                    server_default=True,
                    description="One Kerniq for every client. Chats are separated by a cookie. Models stay loaded and new work waits. Listens on 0.0.0.0 after a restart.",
                ),
                SettingField(
                    key="lan_access",
                    label="Allow LAN access",
                    type=SettingType.BOOL,
                    default=False,
                    server_default=True,
                    description="Bind 0.0.0.0 for LAN (also enabled by server mode)",
                ),
                SettingField(
                    key="show_footer",
                    label="Show status footer",
                    type=SettingType.BOOL,
                    default=True,
                    description="Bottom status bar with provider and tok/s",
                ),
                SettingField(
                    key="ui_locale",
                    label="UI language",
                    type=SettingType.STRING,
                    default="en",
                    description="Interface language. English is built in. Other languages are imported packs.",
                ),
                SettingField(
                    key="log_level",
                    label="Console log level",
                    type=SettingType.SELECT,
                    default="warning",
                    description="How much the terminal prints while UI runs",
                    options=[
                        {"value": "debug", "label": "Debug (verbose)"},
                        {"value": "info", "label": "Info"},
                        {"value": "warning", "label": "Warnings only"},
                        {"value": "error", "label": "Errors only"},
                        {"value": "critical", "label": "Critical only"},
                    ],
                ),
            ],
        )

    def apply_settings(self, values):
        if not values:
            return
        self._ui_host = values.get("host", "127.0.0.1")
        self._ui_port = int(values.get("port", 8765))
        self._server_mode = bool(values.get("server_mode", False))
        if self._server_mode or values.get("lan_access"):
            self._ui_host = "0.0.0.0"
        lvl = str(values.get("log_level") or "warning").upper()
        level = getattr(logging, lvl, logging.WARNING)
        logging.getLogger().setLevel(level)
        for name in ("httpx", "httpcore", "Kerniq", "plugin", "plugin.web_ui", "cli"):
            logging.getLogger(name).setLevel(level)

    async def initialize(self, context: PluginContext) -> bool:
        STATE.context = context
        STATE.history = None
        config_host, config_port = "127.0.0.1", 8765
        state_dir = None
        cfg = getattr(context, "config", None)
        try:
            ui = getattr(cfg, "ui", None)
            if ui is not None:
                config_host = str(getattr(ui, "host", config_host) or config_host)
                config_port = int(getattr(ui, "port", config_port) or config_port)
            storage = getattr(cfg, "storage", None)
            if storage is not None:
                state_dir = getattr(storage, "state_dir", None)
        except Exception:
            logger.exception("ui config was not read")
        if not state_dir:
            state_dir = _state_dir()
        vals: Dict[str, Any] = {}
        try:
            from Kerniq.settings.component_store import ComponentSettingsStore

            vals = ComponentSettingsStore(state_dir).load(
                "plugin", "plugin_web_ui", self.settings_schema()
            )
            self.apply_settings(vals)
        except Exception:
            logger.exception("web ui settings were not loaded")
        from Kerniq.server.listen import resolve_listen
        from Kerniq.server.settings import ensure_api_key, load_server_settings

        core = load_server_settings(state_dir, cfg)
        cli_host = os.environ.get("KERNIQ_CLI_HOST") or None
        cli_port_text = os.environ.get("KERNIQ_CLI_PORT") or ""
        cli_port = int(cli_port_text) if cli_port_text.isdigit() else None
        resolved = resolve_listen(
            config_host=config_host,
            config_port=config_port,
            plugin=vals,
            core=core,
            cli_host=cli_host,
            cli_port=cli_port,
        )
        host = str(resolved["host"])
        port = int(resolved["port"])
        server_mode = bool(resolved["server_mode"])
        self._ui_host = host
        self._ui_port = port
        self._server_mode = server_mode
        STATE.host, STATE.port = host, port
        STATE.server_mode = server_mode
        if server_mode:
            try:
                store = _history_store()
                if store.warning:
                    logger.warning("%s", store.warning)
                    print(store.warning, flush=True)
            except Exception:
                logger.exception("history store")
            try:
                key, created = ensure_api_key(state_dir)
                if created:
                    lan = _detect_lan_ip()
                    print(
                        "Remote consoles need this server address and API key:\n"
                        f"  kerniq run --server http://{lan}:{port} --api-key {key} --task \"...\"\n"
                        "The key is not an address. Run `kerniq server key` to show it again.",
                        flush=True,
                    )
            except Exception:
                logger.exception("api key was not prepared")

        def serve() -> None:
            try:
                ThreadingHTTPServer.allow_reuse_address = True
                httpd = ThreadingHTTPServer((host, port), UIHandler)
            except OSError as e:
                logger.error("Failed to bind Web UI on %s:%s — %s", host, port, e)
                return
            STATE.server = httpd
            _write_ui_pid(context)
            from Kerniq.server.firewall import listen_lines, try_open_port

            note = try_open_port(port) if host in ("0.0.0.0", "::") else ""
            STATE.firewall_note = note
            for line in listen_lines(host, port, firewall_note=note):
                logger.info("%s", line)
                print(line, flush=True)
            try:
                httpd.serve_forever()
            except Exception:
                logger.exception("Web UI server crashed")

        threading.Thread(target=serve, name="kerniq-web-ui", daemon=True).start()
        if context.logger:
            context.logger.info("Web UI at http://%s:%s", host, port)
            if host in ("0.0.0.0", "::") or server_mode:
                context.logger.info("Open from LAN: http://%s:%s", _detect_lan_ip(), port)
        return True

    async def shutdown(self) -> None:
        _clear_ui_pid(STATE.context)
        if STATE.server:
            STATE.server.shutdown()
            STATE.server = None
