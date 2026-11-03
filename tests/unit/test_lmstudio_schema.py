"""LM Studio tool schemas must not put an object in a Jinja boolean test."""

from pathlib import Path

from Kerniq.interfaces.models import Message, MessageRole
from Kerniq.models.text_tools import soften_schema_for_lmstudio
from Kerniq.sandbox.venv import apply_sandbox_env
from Kerniq.server.firewall import announce_listen


def test_array_items_stay_an_object():
    schema = soften_schema_for_lmstudio({
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                },
            },
            "paths": {"type": "array"},
        },
    })
    prop = schema["properties"]["items"]
    assert isinstance(prop["items"], dict)
    assert prop["items"]["type"] == "object"
    assert prop["items"]["properties"]["title"]["type"] == "string"
    assert "Each item is JSON" not in str(prop.get("description") or "")
    assert schema["properties"]["paths"]["items"] == {"type": "string"}


def test_listen_banner_prints_once():
    from Kerniq.server import firewall

    firewall._announced_binds.clear()
    first = announce_listen("0.0.0.0", 8765)
    second = announce_listen("0.0.0.0", 8765)
    assert first and first[0].startswith("Web UI listening")
    assert second == []


def test_host_freedom_keeps_host_programs(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    python = bindir / "python"
    python.write_text("x", encoding="utf-8")
    monkeypatch.setattr("Kerniq.sandbox.venv.ensure_sandbox_python", lambda workspace: python)
    monkeypatch.setattr("Kerniq.sandbox.venv.install_guard", lambda _python: None)
    env = apply_sandbox_env(
        {"PATH": "/usr/bin:/bin"},
        tmp_path,
        confine=False,
        use_venv=True,
    )
    assert "/usr/bin" in env["PATH"]
    assert str(bindir.resolve()) in env["PATH"]
    left = apply_sandbox_env({"PATH": "/usr/bin:/bin", "VIRTUAL_ENV": "/old"}, tmp_path, use_venv=False)
    assert "VIRTUAL_ENV" not in left
    assert "/usr/bin" in left["PATH"]
    assert ".kerniq-venv" not in left["PATH"]


def test_compact_memory_is_in_the_system_prompt_and_keeps_the_setting():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    spec = importlib.util.spec_from_file_location("context_compact_fix", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.PluginImpl()
    plugin.cfg_keep_last = 3
    messages = [
        Message(role=MessageRole.SYSTEM, content="You are Kerniq."),
        Message(role=MessageRole.USER, content="original request"),
        Message(role=MessageRole.ASSISTANT, content="edited plugins/web_ui/main.py and found the race"),
        Message(role=MessageRole.USER, content="continue"),
        Message(role=MessageRole.ASSISTANT, content="tail-a"),
        Message(role=MessageRole.USER, content="tail-b"),
    ]
    out = plugin.compact(messages, summary="Kept the edit to main.py and the race.")
    assert out[0].role == MessageRole.SYSTEM
    assert "Kept the edit to main.py" in out[0].content
    assert out[0].content.startswith("You are Kerniq.")
    body = [m for m in out if m.role != MessageRole.SYSTEM]
    assert len(body) == 3
    assert body[0].content == "original request"
    assert "edited plugins/web_ui/main.py" not in "\n".join(m.content for m in body)
    assert "race" in out[0].content
