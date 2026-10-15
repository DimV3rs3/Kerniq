"""Cursor-like Web UI plugin — explorer, editor, chat, settings tabs."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading
import uuid
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.plugins.manifest import PluginManifest
from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType

logger = logging.getLogger("plugin.web_ui")

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _is_junk_model(model: Dict[str, Any]) -> bool:
    """Embeddings and rerankers are not chat models."""
    kind = str(model.get("type") or "").lower()
    name = str(model.get("id") or model.get("name") or "").lower()
    if kind in ("embedding", "embeddings", "reranker"):
        return True
    return any(tok in name for tok in ("embed", "embedding", "rerank"))


def _heuristic_title(text: str) -> str:
    words = [w for w in (text or "").split() if w]
    out: list[str] = []
    chars = 0
    for word in words:
        if len(out) >= 4:
            break
        if len(out) >= 2 and chars + len(word) > 28:
            break
        out.append(word)
        chars += len(word) + 1
    return " ".join(out) or "Chat"



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


STATE = _State()
from Kerniq.security.approval_broker import ApprovalBroker

STATE.approvals = ApprovalBroker()


def _json(handler: BaseHTTPRequestHandler, code: int, payload: Any) -> None:
    body = json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
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


def _workspace() -> Path:
    store = _settings_store()
    ws = Path(store.load().agent.workspace or "./workspace")
    ws.mkdir(parents=True, exist_ok=True)
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
        self.send_header("Access-Control-Allow-Origin", "*")
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
        if path == "/api/tools":
            return _json(self, 200, self._tools())
        if path == "/api/plugins":
            return _json(self, 200, self._plugins())
        if path == "/api/models":
            return _json(self, 200, self._models())
        if path == "/api/lms/loaded":
            return _json(self, 200, self._lms_loaded())
        if path == "/api/fs/tree":
            return _json(self, 200, self._tree())
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
        if path == "/api/fs/rename":
            return _json(self, 200, self._rename(data))
        if path == "/api/fs/reveal":
            return _json(self, 200, self._reveal(data))
        if path == "/api/fs/pick_folder":
            return _json(self, 200, self._pick_folder())
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
        if STATE.context and STATE.context.tool_registry:
            for t in STATE.context.tool_registry.list_tools():
                tools.append(
                    {"name": t.name, "id": t.tool_id, "description": t.description}
                )
        if not tools:
            try:
                from Kerniq.tools.loader import load_all_tools

                for t in load_all_tools(str(_workspace())):
                    tools.append(
                        {"name": t.name, "id": t.tool_id, "description": t.description}
                    )
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
            models = asyncio.run(provider.list_models())
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

    def _tree(self) -> Dict[str, Any]:
        try:
            ws = _workspace()
            entries = []
            max_entries = 2000

            def walk(dir_path: Path, prefix: str, depth: int) -> None:
                if len(entries) >= max_entries or depth > 12:
                    return
                try:
                    kids = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                except OSError:
                    return
                for p in kids:
                    if len(entries) >= max_entries:
                        return
                    name = p.name
                    rel = f"{prefix}/{name}" if prefix else name
                    rel = rel.replace(chr(92), "/")
                    hidden = name.startswith(".")
                    if p.is_dir():
                        entries.append({"path": rel, "type": "dir", "name": name, "hidden": hidden})
                        walk(p, rel, depth + 1)
                    else:
                        entries.append({"path": rel, "type": "file", "name": name, "hidden": hidden})

            walk(ws, "", 0)
            return {"entries": entries, "workspace": str(ws)}
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
            store = self._component_store()
            for tool in instances:
                try:
                    schema = tool.settings_schema()
                    from Kerniq.tools.runtime_settings import ensure_common_fields

                    schema = ensure_common_fields(schema, tool)
                    values = store.load("tool", tool.tool_id, schema) if schema else {}
                    if "collapsible" in values:
                        try:
                            tool.apply_settings({"collapsible": values["collapsible"]})
                        except Exception:
                            pass
                    tools.append({
                        "id": tool.tool_id,
                        "name": tool.name,
                        "description": tool.description or "",
                        "category": getattr(tool, "category", "other") or "other",
                        "pack_id": getattr(tool, "pack_id", None) or getattr(tool, "category", "other"),
                        "ui_icon": getattr(tool, "ui_icon", "⚙"),
                        "collapsible": bool(getattr(tool, "collapsible", False)),
                        "risk_level": getattr(tool, "risk_level", "medium"),
                        "auto_accept": bool(getattr(tool, "cfg_auto_accept", False)),
                        "chat_label": tool.chat_label(1) if hasattr(tool, "chat_label") else tool.name,
                        "enabled": True,
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

            # Prefer each plugin's own settings_schema() — single source of truth for UI + CLI
            plugin_instances = []
            try:
                plugin_instances.append(PluginImpl())
            except Exception:
                pass
            try:
                import importlib.util
                cc_path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
                # repo layout: examples/plugins/web_ui -> project root is parents[2]
                root = Path(__file__).resolve()
                for _ in range(6):
                    if (root / "plugins" / "context_compact" / "main.py").exists():
                        cc_path = root / "plugins" / "context_compact" / "main.py"
                        break
                    root = root.parent
                if cc_path.exists():
                    spec = importlib.util.spec_from_file_location("context_compact_plugin", cc_path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    plugin_instances.append(mod.PluginImpl())
            except Exception as ex:
                logger.warning("context_compact schema load: %s", ex)

            for inst in plugin_instances:
                try:
                    sch = inst.settings_schema() if hasattr(inst, "settings_schema") else None
                    mid = None
                    try:
                        mid = inst.manifest.plugin_id
                        mname = inst.manifest.name
                    except Exception:
                        mid = getattr(sch, "component_id", None) if sch else "unknown"
                        mname = mid
                    if sch:
                        plugins.append({
                            "id": sch.component_id or mid,
                            "name": sch.title or mname,
                            "status": "available",
                            "schema": sch.to_public(),
                            "values": store.load("plugin", sch.component_id, sch),
                        })
                    else:
                        plugins.append({
                            "id": mid,
                            "name": mname,
                            "status": "available",
                            "schema": None,
                            "values": {},
                        })
                except Exception as ex:
                    logger.exception("plugin schema: %s", ex)
                    try:
                        plugins.append({
                            "id": inst.manifest.plugin_id,
                            "name": inst.manifest.name,
                            "status": "error",
                            "schema": None,
                            "values": {},
                            "error": str(ex),
                        })
                    except Exception:
                        pass
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
        # also persist enabled map into ui_settings tools.enabled_tools
        if enabled is not None and kind == "tool":
            ui = _settings_store()
            cur = ui.load()
            et = dict(cur.tools.enabled_tools or {})
            et[cid] = bool(enabled)
            # also by name
            for item in listing["tools"]:
                if item["id"] == cid:
                    et[item["name"]] = bool(enabled)
            ui.update({"tools": {"enabled_tools": et}})
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
                    if len(hits) >= 40:
                        break
        except Exception as e:
            return {"hits": [], "error": str(e)}
        return {"hits": hits}

    def _import_attachment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Copy an external file into workspace/attachments (sandbox)."""
        import shutil
        src = (data.get("source") or "").strip()
        name = (data.get("name") or "").strip()
        content_b64 = data.get("content_base64")
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
            sp = Path(src)
            if not sp.is_file():
                return {"error": "source not a file"}
            # security: only allow if under workspace OR explicit import into attachments
            try:
                rel_ws = sp.resolve().relative_to(ws.resolve())
                return {"ok": True, "path": str(rel_ws).replace(chr(92), "/"), "workspace_relative": True}
            except ValueError:
                pass
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
<<<<<<< HEAD

    def _chat_title(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prefer a loaded embedding model for the title. Otherwise the usual short title."""
        text = str((data or {}).get("text") or "").strip()
        fallback = _heuristic_title(text)
        ui = _settings_store().load()
        if (ui.api.provider or "lm_studio") != "lm_studio":
            return {"title": fallback, "source": "heuristic"}
        try:
            provider = self._lms_provider()
            models = asyncio.run(provider.list_models())
        except Exception as exc:
            return {"title": fallback, "source": "heuristic", "error": str(exc)}
        embed = next((m for m in models if _is_junk_model(m) and m.get("id")), None)
        if not embed:
            return {"title": fallback, "source": "heuristic"}
        try:
            asyncio.run(provider.load_model(str(embed["id"])))
        except Exception as exc:
            logger.info("embedding load for title skipped: %s", exc)
            return {"title": fallback, "source": "heuristic"}
        try:
            from uuid import uuid4

            from Kerniq.interfaces.models import GenerationOptions, Message, MessageRole, ModelRequest

            previous = provider.model
            provider.model = str(embed["id"])
            request = ModelRequest(
                messages=[
                    Message(
                        role=MessageRole.SYSTEM,
                        content="Reply with a chat title of at most four words. No quotes.",
                    ),
                    Message(role=MessageRole.USER, content=text[:500]),
                ],
                session_id=uuid4(),
                tools=None,
                options=GenerationOptions(temperature=0.2, max_tokens=16, streaming=False),
                metadata={"kerniq_internal": "title"},
            )
            response = asyncio.run(provider.generate(request))
            provider.model = previous
            raw = ""
            if response and response.messages:
                raw = (response.messages[0].content or "").strip().splitlines()[0][:80]
            if raw:
                return {"title": raw, "source": "embedding"}
        except Exception as exc:
            logger.info("embedding title failed, using heuristic: %s", exc)
        return {"title": fallback, "source": "heuristic"}
=======
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f

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
        """Stop HTTP server after response is sent."""
        import threading

        def _stop():
            import time
            time.sleep(0.4)
            try:
                srv = STATE.server
                if srv is not None and hasattr(srv, "shutdown"):
                    srv.shutdown()
            except Exception:
                pass
            try:
                import os
                os._exit(0)
            except Exception:
                pass

        threading.Thread(target=_stop, daemon=True).start()
        return {"ok": True, "message": "shutting down"}

    def _lms_unload_all(self):
        try:
            res = asyncio.run(self._lms_provider().unload_all())
            return {"ok": True, "result": res}
        except Exception as e:
            return {"error": str(e)}

    def _cancel_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = (data or {}).get("run_id") or ""
        with STATE.runs_lock:
            run = STATE.runs.get(run_id)
            if not run:
                return {"ok": False, "error": "run not found"}
            run["cancelled"] = True
            # Do not mark done immediately — worker emits final status and sets done
            run.setdefault("events", []).append(
                {"type": "status", "status": "cancelled", "text": "Stopping…"}
            )
        return {"ok": True, "run_id": run_id}

    def _start_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        run_id = str(uuid.uuid4())
        chat_id = str((data or {}).get("chat_id") or "default")
        with STATE.runs_lock:
            STATE.runs[run_id] = {
                "events": [],
                "log": [],
                "done": False,
                "error": None,
                "chat_id": chat_id,
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
    from Kerniq.sessions.chat_log import ChatLog
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
            from Kerniq.sessions.manager import SessionManager
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
        open_items = [
            item for item in (items or [])
            if isinstance(item, dict) and item.get("status") != "done"
        ]
        _emit(run_id, {
            "type": "plan",
            "items": open_items,
            "archive": list(archive or []),
        })

    agent.orchestrator.on_plan = _on_plan
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
            agent.orchestrator.compactor.cfg_context_limit = 0
    except Exception:
        logger.exception("plugin load during chat run failed")
    if ui.agent.max_iterations is not None:
        agent.orchestrator.max_iterations = ui.agent.max_iterations
    from Kerniq.interfaces.models import GenerationOptions
    agent.orchestrator.generation_options = GenerationOptions(
        temperature=ui.api.temperature if ui.api.temperature is not None else 0.7,
        max_tokens=ui.api.max_tokens,
        streaming=bool(getattr(ui, "chat", None) and ui.chat.streaming),
    )
    # Model context window for overflow protection (best-effort)
    ctx_lim = 0
    try:
<<<<<<< HEAD
        models = await provider.list_models() if hasattr(provider, "list_models") else []
=======
        models = asyncio.run(provider.list_models()) if hasattr(provider, "list_models") else []
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
        want = (ui.api.model or "").strip()
        for m in models or []:
            lim = (
                m.get("loaded_context_length")
                or m.get("context_length")
                or m.get("max_context_length")
                or m.get("context")
            )
            if not lim:
                continue
            mid = str(m.get("id") or m.get("key") or "")
            if want and (mid == want or want in mid or mid in want):
                ctx_lim = int(lim)
                break
            if not ctx_lim:
                ctx_lim = int(lim)
    except Exception:
        pass
    agent.orchestrator.context_limit = ctx_lim or 32768
<<<<<<< HEAD
    compactor = getattr(agent.orchestrator, "compactor", None)
    if compactor is not None:
        compactor.cfg_context_limit = ctx_lim or getattr(compactor, "cfg_max_tokens", 0) or 0
    retries = int(getattr(ui.agent, "loop_retries", None) or 4)
    agent.orchestrator.max_content_loop_hits = max(1, retries)
    agent.orchestrator.max_identical_tool_streak = max(2, retries)
    agent.orchestrator.max_plan_continuations = max(1, retries)
=======
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f

    orig_generate = provider.generate

    def _is_cancelled() -> bool:
        with STATE.runs_lock:
            return bool(STATE.runs.get(run_id, {}).get("cancelled"))

    async def generate_with_status(request):
<<<<<<< HEAD
        if (request.metadata or {}).get("kerniq_internal"):
            return await orig_generate(request)
=======
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
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
        reasoning = None
        if resp.metadata:
            reasoning = resp.metadata.get("reasoning")
        if not reasoning:
            for msg in resp.messages:
                if msg.metadata and msg.metadata.get("reasoning"):
                    reasoning = msg.metadata.get("reasoning")
        if reasoning and str(reasoning).strip():
            _emit(run_id, {"type": "think_done", "text": reasoning})
        # empty final content marker
        texts = [m.content for m in resp.messages if (m.content or "").strip()]
        if not texts and not any(m.tool_calls for m in resp.messages):
            _emit(run_id, {"type": "status", "status": "empty_done", "text": "Model finished (empty response)"})
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
                        (result.error or "")[:200]
                        if (getattr(result, "success", True) is False or result.status == "error")
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
    # 1) server-side store for this chat
    with STATE.chat_lock:
        stored = list(STATE.chat_histories.get(chat_id) or [])
    for h in stored:
        role = h.get("role")
        content = h.get("content") or ""
        if role in ("user", "assistant") and content:
            history_msgs.append(Message(role=MessageRole(role), content=content))
    # 2) client history if longer (browser may have more)
    try:
        client_hist = data.get("history") or []
        if len(client_hist) > len(history_msgs):
            history_msgs = []
            for h in client_hist:
                role = h.get("role")
                content = h.get("content") or ""
                if role in ("user", "assistant") and content:
                    history_msgs.append(Message(role=MessageRole(role), content=content))
    except Exception:
        logger.exception("client history parse")

    system = (ui.prompt.system_prompt or "").strip() or None
    # File reference protocol for the UI
    file_link_hint = (
        "When referring to project files, write links as [[file:relative/path]] "
        "(workspace-relative). The UI will open them in the editor. "
        "Do not invent paths."
    )
    if system:
        system = system.rstrip() + "\n\n" + file_link_hint
    else:
        system = file_link_hint
    if ui.prompt.include_tool_catalog:
        tools_desc = ", ".join(t.name for t in reg.list_tools())
        if tools_desc:
            system = (system or "") + f"\n\nAvailable tools: {tools_desc}."

    # Never bake system into task
    user_task = (task or "").strip()
    if user_task.startswith("[System]") or user_task.startswith("[system]"):
        # client bug — extract user part only
        import re as _re
        mm = _re.search(r"\[User\]\s*(.*)$", user_task, flags=_re.S | _re.I)
        if mm:
            user_task = mm.group(1).strip()

    logger.info(
        "run chat_id=%s history=%s system_len=%s task=%r",
        chat_id, len(history_msgs), len(system or ""), user_task[:120],
    )
    lang = getattr(getattr(ui, "chat", None), "response_language", None) or "auto"
    agent.response_language = lang
<<<<<<< HEAD
    allowed_files = []
    for item in data.get("attachments") or []:
        path = item.get("path") if isinstance(item, dict) else str(item)
        path = str(path or "").replace("\\", "/").lstrip("./")
        if path:
            allowed_files.append(path)
    strict = bool(allowed_files) or bool(getattr(cfg.security, "strict_attachments", False))
    if allowed_files:
        system = (system or "") + (
            "\n\nStrict attachment mode is on. You may only read or write these workspace paths: "
            + ", ".join(allowed_files)
            + ". Other paths will be denied."
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

    async def _verdict(task_text: str) -> str:
        from uuid import uuid4

        from Kerniq.interfaces.models import GenerationOptions, Message, MessageRole, ModelRequest

        request = ModelRequest(
            messages=[
                Message(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You route one user request by complexity. Reply with a single word: PLAN or ACT. "
                        "PLAN if the work is large, unfamiliar, or spans several files or steps. "
                        "Plan mode only writes a detailed TODO. It does not edit anything. "
                        "ACT if the work is small: one script, one obvious edit, or a direct question. "
                        "Act still keeps a short TODO and then does the work. "
                        "A TODO exists in both modes. The word you return only chooses the mode."
                    ),
                ),
                Message(role=MessageRole.USER, content=(task_text or "")[:4000]),
            ],
            session_id=uuid4(),
            tools=None,
            options=GenerationOptions(temperature=0, max_tokens=8, streaming=False),
            metadata={"kerniq_internal": "route"},
        )
        try:
            response = await provider.generate(request)
            text = ""
            if response and response.messages:
                text = (response.messages[0].content or "").strip().upper()
        except Exception:
            logger.exception("plan/act verdict failed")
            return "plan" if compose_plan else "act"
        if text.startswith("ACT"):
            return "act"
        return "plan"

    if mode_auto:
        mode = await _verdict(user_task)
    _emit(run_id, {"type": "mode", "mode": mode})

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
        )

    try:
        result = await _one(user_task, history_msgs or None, mode, initial_plan)
=======
    try:
        result = await agent.run(
            user_task,
            workspace=str(ws),
            system_prompt=system,
            history=history_msgs or None,
            response_language=lang,
        )
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
    except Exception as e:
        if _is_cancelled():
            _emit(run_id, {"type": "status", "status": "cancelled", "text": "Stopped"})
            _emit(run_id, {"type": "assistant", "content": "", "completed": False})
        else:
            msg = str(e)
            _emit(run_id, {"type": "status", "status": "error", "text": "Error"})
            _emit(run_id, {"type": "assistant", "content": f"Error: {msg}", "completed": False})
<<<<<<< HEAD
        _finish_run(run_id, None if _is_cancelled() else str(e))
=======
        with STATE.runs_lock:
            if run_id in STATE.runs:
                STATE.runs[run_id]["done"] = True
                STATE.runs[run_id]["error"] = None if _is_cancelled() else str(e)
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
        return

    if _is_cancelled():
        _emit(run_id, {"type": "status", "status": "cancelled", "text": "Stopped"})
        _emit(run_id, {"type": "cleanup_think"})
<<<<<<< HEAD
        _finish_run(run_id, None)
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

    def _visible(items):
        return [
            item for item in (items or [])
            if isinstance(item, dict) and item.get("status") != "done"
        ]

    plan_items = _plan_items()
    if plan_items or (agent.last_context and (agent.last_context.metadata or {}).get("plan_archive")):
        _emit(run_id, {
            "type": "plan",
            "items": _visible(plan_items),
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
        "max_iterations",
    }
    failed = outcome in fail_outcomes
    open_items = [item for item in plan_items if isinstance(item, dict) and item.get("status") != "done"]
    handoff = (
        mode == "plan"
        and (mode_auto or compose_plan or auto_act)
        and not failed
        and not _is_cancelled()
    )
    if handoff:
        _emit(run_id, {"type": "mode", "mode": "act"})
        _emit(run_id, {"type": "status", "status": "processing", "text": "Act"})
        import json as _json
        archive = []
        if agent.last_context is not None:
            archive = list((agent.last_context.metadata or {}).get("plan_archive") or [])
        act_task = (
            "Plan mode is finished. You are now in ACT. Execute the TODO. Do not spend this turn rewriting a plan instead of working. "
            "Keep the TODO with update_plan. Exactly one item is active. "
            "Mark an item done only after that step is really finished. "
            "Do not repeat archived done items. "
            "Do not stop while any item is pending or active.\n"
            "Open TODO:\n"
            + _json.dumps(_visible(plan_items), ensure_ascii=False)
            + "\nArchived done:\n"
            + _json.dumps(archive, ensure_ascii=False)
            + "\n\nOriginal request:\n"
            + user_task
        )
        hist2 = list(history_msgs)
        hist2.append(Message(role=MessageRole.USER, content=user_task))
        try:
            act_result = await _one(act_task, hist2, "act", _visible(plan_items), archive)
        except Exception as e:
            if _is_cancelled():
                _emit(run_id, {"type": "status", "status": "cancelled", "text": "Stopped"})
                _finish_run(run_id, None)
                return
            _emit(run_id, {"type": "assistant", "content": f"Error: {e}", "completed": False})
            _finish_run(run_id, str(e))
            return
        if _is_cancelled():
            _emit(run_id, {"type": "status", "status": "cancelled", "text": "Stopped"})
            _finish_run(run_id, None)
            return
        plan_items = _plan_items() or plan_items
        if plan_items or archive:
            _emit(run_id, {
                "type": "plan",
                "items": _visible(plan_items),
                "archive": list((agent.last_context.metadata or {}).get("plan_archive") or archive) if agent.last_context else archive,
            })
        outcome = _outcome()
        if isinstance(act_result, str) and "TASK_COMPLETED" in act_result:
            act_result = act_result.replace("TASK_COMPLETED", "").rstrip()
        result = act_result
        failed = outcome in fail_outcomes
=======
        with STATE.runs_lock:
            if run_id in STATE.runs:
                STATE.runs[run_id]["done"] = True
        return

    completed = True
    if isinstance(result, str) and "TASK_COMPLETED" in result:
        result = result.replace("TASK_COMPLETED", "").rstrip()
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
    with STATE.chat_lock:
        lst = STATE.chat_histories.setdefault(chat_id, [])
        lst.append({"role": "user", "content": user_task})
        if result:
            lst.append({"role": "assistant", "content": result})
        if len(lst) > 200:
            STATE.chat_histories[chat_id] = lst[-200:]
<<<<<<< HEAD
    final_status = "error" if failed else "done"
    still_open = [
        item for item in (_plan_items() or plan_items)
        if isinstance(item, dict) and item.get("status") != "done"
    ]
    completed = (not failed) and not still_open
    _emit(run_id, {"type": "assistant", "content": result or "", "completed": completed})
    _emit(
        run_id,
        {
            "type": "status",
            "status": final_status,
            "text": outcome or ("Error" if failed else "Done"),
            "completed": not failed,
        },
    )
=======
    _emit(run_id, {"type": "assistant", "content": result or "", "completed": True})
    _emit(run_id, {"type": "status", "status": "done", "text": "Done", "completed": True})
>>>>>>> 40f42b55ff944a9834cde2fa864246295b00a27f
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
                    description="en or ru — interface only; tools/plugins stay English",
                    options=[{"value": "en", "label": "English"}, {"value": "ru", "label": "Русский"}],
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
