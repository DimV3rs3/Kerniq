"""Cursor-like Web UI plugin — explorer, editor, chat, settings tabs."""

from __future__ import annotations

import asyncio
import json
import logging
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

STATIC_DIR = Path(__file__).resolve().parent / "static"

_BLOCKED_ATTACH = {
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "ico", "heic", "heif", "tif", "tiff",
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
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    ta, tb = a.split("/")[-1], b.split("/")[-1]
    return bool(ta and tb and (ta == tb or ta in tb or tb in ta))


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


async def _title_from_loaded_model(provider, model_id: str, text: str) -> str:
    """Ask one already-loaded model for a short title. Restores provider.model."""
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
        return ""
    finally:
        provider.model = saved
    raw = ""
    if response and response.messages:
        raw = response.messages[0].content or ""
    return _clean_title(raw)


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


STATE = _State()
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


def history_message(row: dict):
    from Kerniq.interfaces.models import Message, MessageRole, ToolCall

    if not isinstance(row, dict):
        return None
    role = row.get("role")
    content = row.get("content") or ""
    if role not in ("user", "assistant", "tool"):
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
    return Message(
        role=MessageRole(role),
        content=content,
        tool_calls=calls or None,
        tool_call_id=row.get("tool_call_id") or None,
        name=row.get("name") or None,
    )


def _grant_path(path: str) -> None:
    try:
        STATE.granted_paths.add(str(Path(path).resolve()))
    except Exception:
        return


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
    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    n = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(n) if n else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


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
    store = _settings_store()
    ws = Path(store.load().agent.workspace or "./workspace")
    return ws.resolve()



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
        path, qs = _parse_qs(self.path)
        if path in ("/", "/index.html"):
            return self._file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/static/app.js":
            return self._file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/static/styles.css":
            return self._file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if path.startswith("/static/vendor/"):
            name = path.rsplit("/", 1)[-1]
            safe = name.replace("-", "").replace("_", "").replace(".", "")
            if not safe.isalnum():
                return _json(self, 400, {"error": "bad path"})
            f = STATIC_DIR / "vendor" / name
            ctype = "text/css; charset=utf-8" if name.endswith(".css") else "application/javascript; charset=utf-8"
            return self._file(f, ctype)
        if path == "/api/settings":
            return _json(self, 200, _settings_store().load().model_dump())
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
        if path == "/api/models":
            return _json(self, 200, self._models())
        if path == "/api/lms/loaded":
            return _json(self, 200, self._lms_loaded())
        if path == "/api/fs/tree":
            return _json(self, 200, self._tree(fresh=(qs.get("fresh") == "1")))
        if path == "/api/fs/file":
            return _json(self, 200, self._read_file(qs.get("path", "")))
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
        _json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        path, _ = _parse_qs(self.path)
        data = _read_json(self)
        if path == "/api/settings":
            store = _settings_store()
            store.update(data)
            return _json(self, 200, store.load().model_dump())
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
        if path == "/api/fs/pick_files":
            return _json(self, 200, self._pick_files())
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
        _json(self, 404, {"error": "not found"})

    def do_PUT(self) -> None:
        path, _ = _parse_qs(self.path)
        data = _read_json(self)
        if path == "/api/fs/file":
            return _json(self, 200, self._write_file(data))
        _json(self, 404, {"error": "not found"})

    def do_DELETE(self) -> None:
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

    def _models(self) -> Dict[str, Any]:
        from Kerniq.models.factory import build_provider

        ui = _settings_store().load()
        provider_id = ui.api.provider or "lm_studio"
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
            }
        except Exception as e:
            return {"models": [], "embeddings": [], "reachable": False, "error": str(e), "provider": provider_id}

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
            data = {"entries": entries, "workspace": key}
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

    def _write_file(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rel = data.get("path") or ""
            path = _safe(_workspace(), rel)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data.get("content") or "", encoding="utf-8")
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
            }
            if sch is not None:
                try:
                    item["values"] = store.load("plugin", sch.component_id, sch)
                except Exception:
                    item["values"] = {}
            if err:
                item["error"] = err
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
        except Exception as e:
            logger.exception("list components")
            return {"tools": tools, "plugins": plugins, "error": str(e)}
        return {"tools": tools, "plugins": plugins}

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
        # find schema
        listing = self._list_components()
        coll = listing["tools"] if kind == "tool" else listing["plugins"]
        schema = None
        for item in coll:
            if item["id"] == cid:
                if item.get("schema"):
                    from Kerniq.interfaces.settings_schema import SettingsSchema
                    schema = SettingsSchema(**item["schema"])
                break
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
        return {"ok": True, "values": saved}

    def _reset_settings(self, data):
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
                safe_name = re.sub(r"[^\w.\-]+", "_", name or "upload.bin")[:120]
                dest = att / safe_name
                # unique
                i = 1
                while dest.exists():
                    dest = att / f"{dest.stem}_{i}{dest.suffix}"
                    i += 1
                dest.write_bytes(raw)
                rel = str(dest.relative_to(ws)).replace(chr(92), "/")
                return {"ok": True, "path": rel, "workspace_relative": True}
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
        server_mode = bool(getattr(STATE, "server_mode", False))
        lan = _detect_lan_ip()
        bind = getattr(STATE, "host", "127.0.0.1")
        port = int(getattr(STATE, "port", 8765))
        public = lan if (server_mode or bind in ("0.0.0.0", "::")) else bind
        return {
            "server_mode": server_mode,
            "bind_host": bind,
            "port": port,
            "lan_ip": lan,
            "public_url": f"http://{public}:{port}",
            "local_url": f"http://127.0.0.1:{port}",
            "folder_picker": "manual" if server_mode else "native",
            "note": (
                "Server mode: paths are on the Kerniq host. Use manual workspace path."
                if server_mode
                else "Client mode: OS folder dialog runs on this machine."
            ),
        }

    def _pick_folder(self) -> Dict[str, Any]:
        """Native folder dialog via tkinter (local desktop)."""
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askdirectory(title="Select workspace")
            root.destroy()
            if not path:
                return {"cancelled": True}
            return {"path": path}
        except Exception as e:
            logger.exception("pick_folder")
            return {"error": f"Folder dialog unavailable: {e}"}

    def _pick_files(self) -> Dict[str, Any]:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            paths = filedialog.askopenfilenames(
                title="Attach files",
                filetypes=[
                    ("Documents and code", "*.md *.txt *.py *.js *.ts *.tsx *.jsx *.json *.toml *.yml *.yaml *.html *.css *.rs *.go *.java *.c *.cpp *.h *.cs *.rb *.php *.sh *.sql *.xml *.csv *.vue *.svelte"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
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
        except Exception as e:
            logger.exception("pick_files")
            return {"error": f"File dialog unavailable: {e}"}


    def _lms_provider(self):
        from Kerniq.models.providers.lm_studio import LMStudioProvider
        ui = _settings_store().load()
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
            }
        try:
            loaded = asyncio.run(self._lms_provider().loaded_instances())
            ui = _settings_store().load()
            selected = (ui.api.model or "").strip()

            def _match(a: str, b: str) -> bool:
                if not a or not b:
                    return False
                if a == b:
                    return True
                if a in b or b in a:
                    return True
                ta, tb = a.split("/")[-1], b.split("/")[-1]
                return bool(ta and tb and (ta == tb or ta in tb or tb in ta))

            selected_loaded = bool(
                selected
                and any(
                    _match(str(x.get("model") or x.get("id") or ""), selected)
                    for x in loaded
                )
            )
            return {
                "loaded": loaded,
                "selected_model": selected,
                "conflict": bool(loaded and selected and not selected_loaded),
                "selected_loaded": selected_loaded,
            }
        except Exception as e:
            return {"loaded": [], "error": str(e), "selected_model": "", "conflict": False, "selected_loaded": False}

    def _chat_title(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Title a chat with the local embedding model, then unload only that model.

        The chat model is loaded first (LM Studio only) and is left loaded.
        The embedding model is loaded after it, asked to name the chat, then unloaded.
        If it cannot produce words, the first three words of the prompt are used.
        """
        text = str((data or {}).get("text") or "").strip()
        fallback = _heuristic_title(text)
        try:
            return asyncio.run(self._chat_title_async(text, fallback))
        except Exception as exc:
            logger.info("chat title failed: %s", exc)
            return {"title": fallback, "source": "heuristic", "error": str(exc)}

    async def _chat_title_async(self, text: str, fallback: str) -> Dict[str, Any]:
        from Kerniq.models.providers.lm_studio import LMStudioProvider

        provider = LMStudioProvider(base_url="http://127.0.0.1:1234")
        try:
            models = await provider.list_models()
        except Exception as exc:
            return {"title": fallback, "source": "heuristic", "error": str(exc)}
        embed = next((m for m in models if _is_junk_model(m) and m.get("id")), None)
        if not embed:
            return {"title": fallback, "source": "heuristic"}

        ui = _settings_store().load()
        if str(getattr(ui.api, "provider", "") or "") == "lm_studio":
            selected = str(getattr(ui.api, "model", "") or "").strip()
            chat = None
            if selected:
                chat = next(
                    (
                        m for m in models
                        if m.get("id") and not _is_junk_model(m) and _model_ids_match(str(m.get("id")), selected)
                    ),
                    None,
                )
            if chat is None:
                chat = next(
                    (m for m in models if m.get("id") and not _is_junk_model(m) and (m.get("loaded_instances") or [])),
                    None,
                )
            if chat and not (chat.get("loaded_instances") or []):
                try:
                    await provider.load_model(str(chat["id"]))
                except Exception as exc:
                    logger.info("chat model load before title skipped: %s", exc)

        embed_id = str(embed["id"])
        try:
            await provider.load_model(embed_id)
        except Exception as exc:
            logger.info("embedding load for title skipped: %s", exc)
            return {"title": fallback, "source": "heuristic"}

        title = ""
        processed = False
        try:
            try:
                vector = await provider.embed_text(embed_id, text[:500])
                processed = bool(vector)
            except Exception as exc:
                logger.info("embedding request failed: %s", exc)
            title = await _title_from_loaded_model(provider, embed_id, text)
        finally:
            try:
                await provider.unload_model_instances(embed_id)
            except Exception:
                logger.info("embedding unload failed", exc_info=True)
        if title:
            return {"title": title, "source": "embedding", "embedding": embed_id, "unloaded": True}
        return {
            "title": fallback,
            "source": "heuristic",
            "embedding": embed_id,
            "processed": processed,
            "unloaded": True,
        }

    def _lms_load(self, data):
        try:
            model = data.get("model") or _settings_store().load().api.model
            if not model:
                return {"error": "no model"}
            alongside = bool(data.get("alongside"))
            p = self._lms_provider()
            if not alongside:
                asyncio.run(p.unload_all())
            _emit_status = None
            res = asyncio.run(p.load_model(model))
            return {"ok": True, "result": res}
        except Exception as e:
            return {"error": str(e)}

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
        chat_id = str((data or {}).get("chat_id") or "default")
        with STATE.runs_lock:
            pre_cancelled = chat_id in STATE.cancel_chats
            if pre_cancelled:
                STATE.cancel_chats.discard(chat_id)
            STATE.runs[run_id] = {
                "events": [],
                "log": [],
                "done": False,
                "error": None,
                "chat_id": chat_id,
                "cancelled": pre_cancelled,
            }
        try:
            _chat_log().begin(
                chat_id,
                run_id,
                (data or {}).get("task") or "",
                (data or {}).get("attachments") or [],
            )
        except Exception:
            logger.exception("chat log begin failed")
        threading.Thread(
            target=_run_agent_thread,
            args=(run_id, data.get("task") or "", data),
            daemon=True,
        ).start()
        return {"run_id": run_id}

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
                log = run.get("log") or []
                chunk = log[idx:]
                return {
                    "events": chunk,
                    "done": bool(run.get("done")),
                    "error": run.get("error"),
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
        STATE.chat_log = ChatLog(SettingsProvider().config.storage.state_dir)
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


def _run_agent_thread(run_id: str, task: str, payload: dict | None = None) -> None:
    try:
        asyncio.run(_run_agent_async(run_id, task, payload or {}))
    except Exception as e:
        logger.exception("run failed")
        _emit(run_id, {"type": "assistant", "content": f"Error: {e}"})
        _finish_run(run_id, str(e))


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
    ws = Path(ui.agent.workspace or "./workspace")
    ws.mkdir(parents=True, exist_ok=True)
    ws = ws.resolve()

    _emit(run_id, {"type": "status", "status": "processing", "text": "Processing prompt…"})

    cfg = SettingsProvider().config
    ceiling = getattr(getattr(ui, "chat", None), "auto_approve_up_to", None) or getattr(
        cfg.security, "auto_approve_up_to", "low"
    )
    reg, policy = build_tool_registry(
        ws,
        config=cfg,
        state_dir=cfg.storage.state_dir,
        auto_approve_up_to=ceiling,
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
                workspace=str(ws),
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
        loaded_fallback = 0
        for m in models or []:
            mid = str(m.get("id") or m.get("key") or "")
            if "embed" in mid.lower():
                continue
            lim = (
                m.get("loaded_context_length")
                or m.get("context_length")
                or m.get("max_context_length")
                or m.get("context")
            )
            if m.get("loaded_context_length"):
                loaded_fallback = int(m["loaded_context_length"])
            if not lim:
                continue
            if want and (mid == want or want in mid or mid in want):
                ctx_lim = int(lim)
                break
        if not ctx_lim and loaded_fallback:
            ctx_lim = loaded_fallback
    except Exception:
        pass
    agent.orchestrator.context_limit = int(ctx_lim or 0)
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
            return await orig_generate(request)
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
                })
                _emit(run_id, {
                    "type": "assistant",
                    "content": (
                        "The selected model is not loaded in LM Studio. "
                        "Open LM Studio and load a model, or use API & model settings to load one, then retry."
                    ),
                    "completed": False,
                })
            else:
                _emit(run_id, {"type": "status", "status": "error", "text": "Model error"})
                _emit(run_id, {"type": "assistant", "content": f"Model error: {msg}", "completed": False})
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

        promote_reasoning(resp)
        texts = [m.content for m in resp.messages if (m.content or "").strip()]
        if not texts and not any(m.tool_calls for m in resp.messages):
            _emit(run_id, {"type": "status", "status": "empty_done", "text": "Empty reply, retrying…"})
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
    history_msgs: list = []
    with STATE.chat_lock:
        stored = list(STATE.chat_histories.get(chat_id) or [])
    if not stored:
        try:
            stored = _chat_log().model_messages(chat_id)
        except Exception:
            logger.exception("model history load failed")
            stored = []
        if stored:
            with STATE.chat_lock:
                if not STATE.chat_histories.get(chat_id):
                    STATE.chat_histories[chat_id] = list(stored)
                else:
                    stored = list(STATE.chat_histories[chat_id])
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
    if ui.prompt.include_tool_catalog:
        system = (system or "") + (
            "\n\nCallable tools for each turn are listed at the end of the system message "
            "as [Tools this turn]. Only those may be called. "
            "Until a TODO exists, that list is update_plan and nothing else."
        )

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
                STATE.chat_histories[chat_id] = rows
            try:
                _chat_log().save_model_messages(chat_id, rows)
            except Exception:
                logger.exception("model history persist failed")
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
    for item in data.get("attachments") or []:
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
    if external_files:
        system = (system or "") + (
            "\n\nThese files are outside the workspace. You may read them. "
            "Writing, editing, or deleting them requires user approval:\n"
            + "\n".join(external_files)
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
    agent.orchestrator.finish_open_plan = True
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

    async def _one(task_text, hist, run_mode, plan0, archive0=None):
        return await agent.run(
            task_text,
            workspace=str(ws),
            system_prompt=system,
            history=hist,
            response_language=lang,
            allowed_files=allowed_files or None,
            strict_attachments=strict,
            agent_mode=run_mode,
            initial_plan=plan0,
            plan_archive=archive0,
            plan_handoff=bool(run_mode == "plan" and auto_act),
            external_files=external_files or None,
        )

    if _is_cancelled():
        _finish_cancelled()
        return

    try:
        result = await _one(user_task, history_msgs or None, mode, initial_plan, initial_archive)
    except Exception as e:
        if _is_cancelled():
            _finish_cancelled()
        else:
            title, detail = _public_error(e)
            _emit(run_id, {"type": "status", "status": "error", "text": title})
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
        if agent.last_context is not None:
            prior_rows = transcript_rows(agent.last_context.messages)
        try:
            act_result = await _one(act_task, None, "act", None, research or None)
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
                    description="127.0.0.1 = only local; 0.0.0.0 = LAN",
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
                    description="Remote UI host: auto LAN bind, show LAN IP, disable OS folder dialog for clients",
                ),
                SettingField(
                    key="lan_access",
                    label="Allow LAN access",
                    type=SettingType.BOOL,
                    default=False,
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
                    type=SettingType.SELECT,
                    default="en",
                    description="Interface language. English is built in. Other languages are imported packs.",
                    options=[{"value": "en", "label": "English"}],
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
        host, port = "127.0.0.1", 8765
        cfg = getattr(context, "config", None)
        try:
            ui = getattr(cfg, "ui", None)
            if ui is not None:
                host = getattr(ui, "host", host)
                port = int(getattr(ui, "port", port))
        except Exception:
            pass
        # persisted plugin settings override
        try:
            from Kerniq.settings.component_store import ComponentSettingsStore
            from Kerniq.settings.loader import SettingsProvider
            store = ComponentSettingsStore(SettingsProvider().config.storage.state_dir)
            vals = store.load("plugin", "plugin_web_ui", self.settings_schema())
            self.apply_settings(vals)
            host = getattr(self, "_ui_host", host)
            port = int(getattr(self, "_ui_port", port))
        except Exception:
            pass
        server_mode = bool(getattr(self, "_server_mode", False))
        if server_mode:
            host = "0.0.0.0"
        STATE.host, STATE.port = host, port
        STATE.server_mode = server_mode

        def serve() -> None:
            try:
                httpd = ThreadingHTTPServer((host, port), UIHandler)
            except OSError as e:
                logger.error("Failed to bind Web UI on %s:%s — %s", host, port, e)
                return
            STATE.server = httpd
            logger.info("Web UI listening on http://%s:%s", host, port)
            if host in ("0.0.0.0", "::") or server_mode:
                logger.info(
                    "LAN URL: http://%s:%s (server_mode=%s)",
                    _detect_lan_ip(), port, server_mode,
                )
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
        if STATE.server:
            STATE.server.shutdown()
            STATE.server = None
