"""Plugin lifecycle and Web UI HTTP scenarios. LM Studio is not required."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx

from Kerniq.plugins.base import PluginContext
from Kerniq.plugins.manager import PluginManager
from Kerniq.tools.registry import ToolRegistry


def _plugins_root() -> Path:
    return Path(__file__).resolve().parents[2] / "plugins"


def test_plugin_register_settings_and_shutdown(tmp_path):
    async def go():
        registry = ToolRegistry()
        pm = PluginManager(
            lambda: PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry)
        )
        await pm.discover_and_load(_plugins_root(), skip_ids=["plugin_web_ui"])
        names = {t.name for t in registry.list_tools()}
        offered = {spec["function"]["name"] for spec in registry.get_tools_for_model()}
        assert "plugin_search" in names
        for hidden in (
            "plugin_search",
            "plugin_install",
            "plugin_remove",
            "plugin_security_scan",
            "plugin_list_installed",
        ):
            assert hidden not in offered
        assert "benchmark_run" not in names
        shipped = {
            path.name for path in _plugins_root().iterdir()
            if path.is_dir() and (path / "manifest.toml").is_file()
        }
        assert shipped == {"plugin_manager", "web_ui", "context_compact"}

        from Kerniq.plugins.distribution import inspect_plugin, install_tree
        from Kerniq.plugins.extensions import scan_extensions

        repo = Path(__file__).resolve().parents[2]
        bench = repo / "catalog" / "Kerniq-llm-benchmark"
        compact_dir = _plugins_root() / "context_compact"
        assert inspect_plugin(bench)["standalone"] is True
        assert inspect_plugin(compact_dir)["kit"] is True
        assert inspect_plugin(compact_dir)["standalone"] is False
        assert inspect_plugin(_plugins_root() / "plugin_manager")["kit"] is True
        assert inspect_plugin(_plugins_root() / "web_ui")["kit"] is True
        assert install_tree(bench, plugins_dir=tmp_path)["ok"] is True
        assert install_tree(compact_dir, plugins_dir=tmp_path)["ok"] is False
        assert install_tree(_plugins_root() / "web_ui", plugins_dir=tmp_path)["ok"] is False
        assert (tmp_path / "llm-benchmark" / ".kerniq-origin.json").is_file()
        from Kerniq.plugins.distribution import check_updates, remove_plugin

        assert remove_plugin("plugin_web_ui", confirm=True, plugins_dir=_plugins_root())["ok"] is False
        assert (_plugins_root() / "web_ui" / "manifest.toml").is_file()
        assert remove_plugin("plugin_context_compact", confirm=True, plugins_dir=_plugins_root())["ok"] is False
        assert (_plugins_root() / "context_compact" / "manifest.toml").is_file()
        current = {row["plugin_id"]: row for row in check_updates(tmp_path)}
        assert current["llm-benchmark"]["update"] is False
        bench_manifest = tmp_path / "llm-benchmark" / "manifest.toml"
        bench_manifest.write_text(bench_manifest.read_text(encoding="utf-8").replace('version = "1.1.0"', 'version = "1.0.0"'))
        newer = {row["plugin_id"]: row for row in check_updates(tmp_path)}
        assert newer["llm-benchmark"]["update"] is True
        assert "1.1.0" in newer["llm-benchmark"]["note"]

        compact = pm.plugins["plugin_context_compact"]
        compact.apply_settings({"enabled": False, "keep_last": 3})
        assert compact.cfg_enabled is False
        await pm.shutdown_all()
        assert pm.get_plugin_status("plugin_context_compact").value == "stopped"

        registry2 = ToolRegistry()
        pm2 = PluginManager(
            lambda: PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry2)
        )
        await pm2.discover_and_load(tmp_path)
        names2 = {t.name for t in registry2.list_tools()}
        offered2 = {spec["function"]["name"] for spec in registry2.get_tools_for_model()}
        assert "benchmark_run" in names2
        assert "benchmark_run" not in offered2
        import shutil

        shutil.copytree(_plugins_root() / "web_ui", tmp_path / "web_ui")
        hosts = {(row["host"], row["slot"], row["plugin_id"]) for row in scan_extensions(tmp_path)}
        assert ("plugin_web_ui", "settings", "llm-benchmark") in hosts
        assert ("plugin_web_ui", "panel", "llm-benchmark") in hosts
        await pm2.shutdown_all()
        return names

    names = asyncio.run(go())
    assert "plugin_list_installed" in names


def test_web_ui_run_cancel_and_approval(tmp_path, monkeypatch):
    import importlib.util

    ui_path = _plugins_root() / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_test", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from Kerniq.settings.ui_store import UiSettingsStore

    store = UiSettingsStore(tmp_path / "state")
    ui = store.load()
    ui.api.provider = "mock"
    ui.agent.workspace = str(tmp_path / "ws")
    ui.chat.streaming = False
    ui.chat.compose_plan = False
    ui.chat.mode_auto = False
    store.save(ui)
    (tmp_path / "ws").mkdir()
    monkeypatch.setattr(mod, "_settings_store", lambda: store)
    monkeypatch.setattr(mod, "_workspace", lambda: (tmp_path / "ws").resolve())

    httpd = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.UIHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def call(method, path, payload=None):
        response = httpx.request(
            method,
            f"http://127.0.0.1:{port}{path}",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    try:
        info = call("GET", "/api/server/info")
        assert "host" in info or "port" in info or isinstance(info, dict)
        models = call("GET", "/api/models")
        assert "reachable" in models
        pending = call("GET", "/api/approvals")
        assert pending["pending"] == []
        denied = call("POST", "/api/approvals/decide", {"request_id": "missing", "decision": "allow"})
        assert denied["ok"] is False

        started = call("POST", "/api/chat/run", {"task": "Say hello", "chat_id": "c1", "history": []})
        run_id = started["run_id"]
        seen = []
        done = False
        last = {}
        for _ in range(200):
            ev = call("GET", f"/api/chat/events?run_id={run_id}")
            last = ev
            seen.extend(ev.get("events") or [])
            if ev.get("done"):
                done = True
                break
            threading.Event().wait(0.05)
        assert done, last
        text = " ".join(str(e.get("content") or e.get("text") or "") for e in seen)
        assert "mock provider" in text.lower() or "outcome=" in text, text[:500]

        import Kerniq.core.agent as agent_mod

        original = agent_mod.Agent.run

        async def slow(self, *args, **kwargs):
            await asyncio.sleep(1.2)
            return "should-be-cancelled"

        agent_mod.Agent.run = slow
        try:
            started = call("POST", "/api/chat/run", {"task": "wait", "chat_id": "c2"})
            run_id = started["run_id"]
            cancelled = call("POST", "/api/chat/cancel", {"run_id": run_id})
            assert cancelled["ok"] is True
            done = False
            statuses = []
            for _ in range(160):
                ev = call("GET", f"/api/chat/events?run_id={run_id}")
                for item in ev.get("events") or []:
                    if item.get("type") == "status":
                        statuses.append(item.get("status"))
                if ev.get("done"):
                    done = True
                    break
                threading.Event().wait(0.05)
            assert done
            assert "cancelled" in statuses
            saved = mod.STATE.chat_histories.get("c2") or []
            assert any(item.get("role") == "user" and "wait" in (item.get("content") or "") for item in saved)
            assert any(item.get("role") == "assistant" and "Stopped by the user" in (item.get("content") or "") for item in saved)
            assert "c2" not in mod.STATE.cancel_chats
        finally:
            agent_mod.Agent.run = original
        started = call("POST", "/api/chat/run", {"task": "next question", "chat_id": "c2", "history": []})
        with mod.STATE.runs_lock:
            follow = mod.STATE.runs.get(started["run_id"])
        assert follow is not None
        assert follow.get("cancelled") is False
    finally:
        httpd.shutdown()


def test_stopped_turn_stays_in_model_history():
    import importlib.util

    ui_path = _plugins_root() / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_hist", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    server = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "did the first part"},
    ]
    client = server + [{"role": "user", "content": "continue the same task"}]
    merged = mod.merge_histories(server, client)
    assert merged[-1]["content"] == "continue the same task"

    # Server kept tool calls the browser does not resend. Client is a prefix.
    rich = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "name": "read_file", "arguments": {}}]},
        {"role": "tool", "content": "file body", "tool_call_id": "1", "name": "read_file"},
        {"role": "assistant", "content": "partial reply"},
    ]
    visible = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "partial reply"},
    ]
    assert mod.merge_histories(rich, visible) == rich

    continued = visible + [{"role": "user", "content": "go on from here"}]
    merged = mod.merge_histories(rich, continued)
    assert any(row.get("role") == "tool" for row in merged)
    assert merged[-1]["role"] == "user" and merged[-1]["content"] == "go on from here"

    # Visible text diverged, but the new user turn still has to reach the model.
    diverged = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "something else"},
        {"role": "user", "content": "go on from here"},
    ]
    merged = mod.merge_histories(rich, diverged)
    assert any(row.get("role") == "tool" for row in merged)
    assert merged[-1]["content"] == "go on from here"

    saved = mod.compose_saved_history(
        [{"role": "user", "content": "older"}, {"role": "assistant", "content": "done"}],
        None,
        user_task="do the thing",
        partial="started the patch",
        cancelled=True,
    )
    assert saved[0]["content"] == "older"
    assert saved[-2]["role"] == "user" and saved[-2]["content"] == "do the thing"
    assert "started the patch" in saved[-1]["content"]
    assert "Stopped by the user" in saved[-1]["content"]


def test_cancel_of_a_live_run_does_not_arm_the_next_one():
    import importlib.util

    ui_path = _plugins_root() / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_cancel", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.STATE.runs.clear()
    mod.STATE.cancel_chats.clear()
    mod.STATE.runs["r1"] = {
        "done": False,
        "chat_id": "c",
        "cancelled": False,
        "log": [],
        "events": [],
    }
    handler = mod.UIHandler.__new__(mod.UIHandler)
    result = handler._cancel_run({"run_id": "r1", "chat_id": "c"})
    assert result["ok"] is True
    assert mod.STATE.runs["r1"]["cancelled"] is True
    assert "c" not in mod.STATE.cancel_chats
    armed = handler._cancel_run({"chat_id": "later"})
    assert armed["ok"] is True
    assert "later" in mod.STATE.cancel_chats


def test_duplicate_user_text_is_collapsed():
    import importlib.util

    ui_path = _plugins_root() / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_dup", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    saved = mod.compose_saved_history(
        [
            {"role": "assistant", "content": "Stopped by the user. This reply was not finished. Continue the same task from the work already done. Do not start over."},
            {"role": "user", "content": "а план составлять кто будет?"},
            {"role": "user", "content": "а план составлять кто будет?"},
        ],
        None,
        user_task="а план составлять кто будет?",
        cancelled=False,
    )
    users = [row["content"] for row in saved if row.get("role") == "user"]
    assert users == ["а план составлять кто будет?"]
