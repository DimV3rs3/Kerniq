"""Server mode: bind address, users, JSON history, queue, and plugin -s."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from Kerniq.plugins.cli_settings import apply_named_settings, assign_settings, repair_values
from Kerniq.server.identity import resolve_user
from Kerniq.server.listen import resolve_listen
from Kerniq.server.queue import RunQueue, unload_allowed
from Kerniq.server.remote import remote_required_message
from Kerniq.server.settings import JSON_STORAGE_WARNING, load_server_settings
from Kerniq.server.store import HistoryStore, parse_mysql_url


def test_public_host_wins_over_the_loopback_default():
    decided = resolve_listen(
        config_host="127.0.0.1",
        plugin={"host": "0.0.0.0", "port": 8765, "server_mode": False},
        core={"host": "127.0.0.1", "enabled": False},
    )
    assert decided["host"] == "0.0.0.0"
    assert decided["port"] == 8765


def test_config_public_host_is_not_hidden_by_the_plugin_default():
    decided = resolve_listen(
        config_host="0.0.0.0",
        plugin={"host": "127.0.0.1", "server_mode": False, "lan_access": False},
        core={"host": "127.0.0.1", "enabled": False},
    )
    assert decided["host"] == "0.0.0.0"


def test_server_mode_forces_a_public_bind():
    decided = resolve_listen(
        config_host="127.0.0.1",
        plugin={"host": "127.0.0.1", "server_mode": True},
        core={"host": "127.0.0.1", "enabled": False},
    )
    assert decided["host"] == "0.0.0.0"
    assert decided["server_mode"] is True


def test_explicit_cli_host_wins():
    decided = resolve_listen(
        config_host="0.0.0.0",
        plugin={"host": "0.0.0.0", "server_mode": True},
        cli_host="127.0.0.1",
        cli_port=9000,
    )
    assert decided["host"] == "127.0.0.1"
    assert decided["port"] == 9000
    assert decided["server_mode"] is True


def test_cookie_is_only_an_id_and_a_missing_cookie_is_a_new_user():
    first, created, kind = resolve_user({}, server_mode=True, api_key="secret")
    assert created is True and kind == "cookie" and len(first) == 32
    again, created, kind = resolve_user(
        {"Cookie": f"kerniq_user={first}"},
        server_mode=True,
        api_key="secret",
    )
    assert again == first and created is False and kind == "cookie"
    other, created, _kind = resolve_user({}, server_mode=True, api_key="secret")
    assert created is True and other != first


def test_api_key_is_a_stable_user_and_a_wrong_key_is_refused():
    ok, _created, kind = resolve_user(
        {"Authorization": "Bearer secret"},
        server_mode=True,
        api_key="secret",
    )
    same, _created, kind2 = resolve_user(
        {"X-Kerniq-Key": "secret"},
        server_mode=True,
        api_key="secret",
    )
    assert kind == "api" and kind2 == "api" and ok == same and ok.startswith("api:")
    _uid, _created, denied = resolve_user(
        {"Authorization": "Bearer nope"},
        server_mode=True,
        api_key="secret",
    )
    assert denied == "denied"
    local, created, kind = resolve_user({}, server_mode=False, api_key="")
    assert local == "local" and created is False and kind == "local"


def test_json_history_is_per_user_and_warns_without_mysql(tmp_path):
    store = HistoryStore(tmp_path, "")
    assert store.backend == "json"
    assert store.warning == JSON_STORAGE_WARNING
    store.save_chats("user-a", [{"id": "1", "title": "alpha"}])
    store.save_chats("user-b", [{"id": "2", "title": "beta"}])
    assert store.list_chats("user-a")[0]["title"] == "alpha"
    assert store.list_chats("user-b")[0]["id"] == "2"
    store.save_replies("user-a", "1", [{"role": "assistant", "content": "done"}])
    assert store.replies("user-a", "1")[0]["content"] == "done"
    assert store.replies("user-b", "1") == []


def test_mysql_url_parser_does_not_need_urllib():
    parsed = parse_mysql_url("mysql://kerniq:s3cret@db.internal:3307/kerniq")
    assert parsed["user"] == "kerniq"
    assert parsed["password"] == "s3cret"
    assert parsed["host"] == "db.internal"
    assert parsed["port"] == 3307
    assert parsed["database"] == "kerniq"


def test_server_mode_refuses_unload_and_queues_the_next_task():
    assert unload_allowed(False, "unload") is True
    assert unload_allowed(True, "unload") is False
    assert unload_allowed(True, "unload_busy") is False
    assert unload_allowed(True, "alongside") is True
    queue = RunQueue()
    first = queue.admit("run-a", busy=False)
    second = queue.admit("run-b", busy=True)
    third = queue.admit("run-c", busy=False)
    assert first["queued"] is False
    assert second == {"queued": True, "position": 1}
    assert third["position"] == 2
    assert queue.next() == "run-b"
    assert queue.next() == "run-c"
    assert queue.next() is None


def test_remote_console_must_know_the_address():
    assert "address" in remote_required_message(False, True).lower()
    assert "api-key" in remote_required_message(True, False)
    assert remote_required_message(True, True) == ""


def test_plugin_setting_rejects_a_bad_value_and_keeps_a_good_one():
    schema = SettingsSchema(
        component_id="demo",
        component_type="plugin",
        title="Demo",
        fields=[
            SettingField(
                key="port",
                label="Port",
                type=SettingType.INT,
                default=8765,
                minimum=1,
                maximum=65535,
            ),
            SettingField(
                key="host",
                label="Host",
                type=SettingType.STRING,
                default="127.0.0.1",
            ),
        ],
    )
    _updated, errors = assign_settings(schema, {}, [("port", "nope")])
    assert errors and "port" in errors[0]
    updated, errors = assign_settings(schema, {}, [("host", "0.0.0.0")])
    assert errors == [] and updated["host"] == "0.0.0.0"
    clean, notes = repair_values(schema, {"port": "wide"})
    assert clean["port"] == 8765
    assert any("port" in note for note in notes)


def test_console_set_writes_server_mode_and_refuses_a_bad_port(tmp_path):
    plugins = Path(__file__).resolve().parents[2] / "plugins"
    code, lines = apply_named_settings(tmp_path, "plugin_web_ui", [("port", "nope")], [plugins])
    assert code == 1
    assert any("port" in line for line in lines)
    code, lines = apply_named_settings(
        tmp_path,
        "plugin_web_ui",
        [("host", "0.0.0.0"), ("server_mode", "true")],
        [plugins],
    )
    assert code == 0
    core = load_server_settings(tmp_path)
    assert core["enabled"] is True
    assert core["host"] == "0.0.0.0"


def test_ui_binds_the_saved_public_host(tmp_path, monkeypatch):
    ui_path = Path(__file__).resolve().parents[2] / "plugins" / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_bind", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    captured = []

    class _Server:
        def __init__(self, addr, handler):
            captured.append(addr)
            self.server_address = addr

        def serve_forever(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(mod, "ThreadingHTTPServer", _Server)
    monkeypatch.delenv("KERNIQ_CLI_HOST", raising=False)
    monkeypatch.delenv("KERNIQ_BIND", raising=False)
    monkeypatch.delenv("KERNIQ_SERVER_MODE", raising=False)

    from Kerniq.settings.component_store import ComponentSettingsStore

    store = ComponentSettingsStore(tmp_path)
    schema = mod.PluginImpl().settings_schema()
    store.save("plugin", "plugin_web_ui", {"host": "0.0.0.0", "port": 8765, "server_mode": True}, schema)

    class _UI:
        host = "127.0.0.1"
        port = 8765

    class _Storage:
        state_dir = tmp_path

    class _ServerCfg:
        enabled = False
        host = "127.0.0.1"
        port = 8765
        database_url = ""

    class _Config:
        ui = _UI()
        storage = _Storage()
        server = _ServerCfg()

    import asyncio
    import time

    from Kerniq.plugins.base import PluginContext

    asyncio.run(mod.PluginImpl().initialize(PluginContext(None, _Config(), None, None)))
    for _ in range(50):
        if captured:
            break
        time.sleep(0.02)
    assert captured, "the UI never opened a socket"
    assert captured[0][0] == "0.0.0.0"
    assert mod.STATE.server_mode is True


def test_ui_identify_records_the_request_user():
    ui_path = Path(__file__).resolve().parents[2] / "plugins" / "web_ui" / "main.py"
    spec = importlib.util.spec_from_file_location("kerniq_web_ui_identify", ui_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Handler:
        headers: dict = {}

    mod.STATE.server_mode = False
    handler = Handler()
    user_id, kind = mod._identify(handler)
    assert (user_id, kind) == ("local", "local")
    assert handler._kerniq_user == "local"
    assert mod._ui_user.get() == "local"
    mod._ui_user.set("")
