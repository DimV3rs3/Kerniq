"""Exact model identity, load choices, and text tool calls."""

from Kerniq.models.capabilities import native_tools_enabled, remember_native_tools
from Kerniq.models.identity import instance_model_key, same_model
from Kerniq.models.load_policy import plan_model_load
from Kerniq.models.text_tools import parse_text_tool_calls
from Kerniq.settings.secrets import token_is_plaintext
from Kerniq.settings.ui_store import UiSettingsStore


def test_model_ids_are_exact():
    assert same_model("google/gemma-4-12b", "google/gemma-4-12b")
    assert not same_model("google/gemma-4-12b", "google/gemma-4-12b-qat")
    assert not same_model("gemma", "google/gemma-4-12b")
    assert not same_model("", "google/gemma-4-12b")


def test_busy_foreign_model_cannot_be_unloaded():
    plan = plan_model_load("google/gemma-4-e2b", ["google/gemma-4-12b"], busy=True)
    assert plan.status == "foreign"
    assert [choice.id for choice in plan.choices] == ["alongside", "cancel"]


def test_idle_foreign_model_can_be_unloaded_or_kept():
    plan = plan_model_load("google/gemma-4-e2b", ["google/gemma-4-12b"], busy=False)
    assert [choice.id for choice in plan.choices] == ["unload", "alongside", "cancel"]
    ready = plan_model_load("google/gemma-4-e2b", ["google/gemma-4-e2b"])
    assert ready.status == "ready"
    assert ready.choices == []


def test_instance_suffix_is_the_same_loaded_model():
    assert instance_model_key("google/gemma-4-e2b:2") == "google/gemma-4-e2b"
    assert instance_model_key("google/gemma-4-12b-qat") == "google/gemma-4-12b-qat"
    assert not same_model("google/gemma-4-12b", "google/gemma-4-12b-qat")
    plan = plan_model_load(
        instance_model_key("google/gemma-4-e2b"),
        [instance_model_key("google/gemma-4-e2b:2")],
    )
    assert plan.status == "ready"
    assert plan.selected_loaded is True


def test_unload_uses_the_catalog_key_as_the_instance_id():
    from Kerniq.models.providers.lm_studio import instance_ids_for_unload

    loaded = [
        {"id": "google/gemma-4-e2b"},
        {"id": "google/gemma-4-e2b:2"},
        {"id": "google/gemma-4-12b"},
    ]
    assert instance_ids_for_unload(loaded, "google/gemma-4-e2b") == [
        "google/gemma-4-e2b",
        "google/gemma-4-e2b:2",
    ]
    assert instance_ids_for_unload(loaded, "google/gemma-4-12b") == ["google/gemma-4-12b"]
    assert instance_ids_for_unload(loaded, "google/gemma-4-12b-qat") == []


def test_already_loaded_model_is_not_loaded_again():
    import asyncio
    from types import SimpleNamespace

    from Kerniq.core.runtime_flow import use_model_for_mode

    class Provider:
        provider_id = "lm_studio"
        model = ""
        loads = 0
        unloads = 0

        async def model_is_loaded(self, key):
            return key == "google/gemma-4-e2b"

        async def load_model(self, key):
            self.loads += 1

        async def unload_all(self):
            self.unloads += 1

        async def resolve_auto_model(self):
            return "google/gemma-4-e2b"

    provider = Provider()
    api = SimpleNamespace(model="google/gemma-4-e2b", act_model="", split_models=False, provider="lm_studio")
    assert asyncio.run(use_model_for_mode(provider, api, "act")) is None
    assert provider.loads == 0
    assert provider.unloads == 0
    assert provider.model == "google/gemma-4-e2b"
    api.model = ""
    provider.model = ""
    assert asyncio.run(use_model_for_mode(provider, api, "act")) is None
    assert provider.model == "google/gemma-4-e2b"
    assert provider.loads == 0


def test_textual_tool_call_is_parsed():
    raw = (
        'update_plan{items:[{id:<|"|>1<|"|>,status:<|"|>pending<|"|>,'
        'title:<|"|>Исследовать LM Studio<|"|>}]}'
    )
    cleaned, calls = parse_text_tool_calls(raw, ["update_plan", "web_search"])
    assert len(calls) == 1
    assert calls[0].name == "update_plan"
    assert calls[0].arguments["items"][0]["status"] == "pending"
    assert "update_plan" not in cleaned


def test_written_function_call_with_verbatim_body_is_a_tool_call():
    raw = '''Начинаю реализацию.
write_file("CalculatorCore/IMathOperation.cs", @"
using System;
namespace CalculatorCore
{
    public class C { public double Execute(double a, double b) { return a + b; } }
}
}"<|"|>,path:<|"|>CalculatorCore/IMathOperation.cs<|"|>,replace_all:true}<tool_call|>
'''
    cleaned, calls = parse_text_tool_calls(
        raw,
        ["write_file", "edit_file"],
        {"write_file": ["path", "content", "create_dirs"]},
    )
    assert len(calls) == 1
    assert calls[0].name == "write_file"
    assert calls[0].arguments["path"] == "CalculatorCore/IMathOperation.cs"
    assert "public double Execute(double a, double b)" in calls[0].arguments["content"]
    assert calls[0].arguments["replace_all"] is True
    assert "write_file" not in cleaned
    assert "Начинаю реализацию." in cleaned


def test_closed_function_call_uses_named_arguments():
    raw = 'read_file(path=<|"|>src/App.xaml.cs<|"|>)'
    cleaned, calls = parse_text_tool_calls(raw, ["read_file"], {"read_file": ["path"]})
    assert len(calls) == 1
    assert calls[0].arguments["path"] == "src/App.xaml.cs"
    assert cleaned == ""


def test_textual_plan_array_is_a_tool_call():
    raw = """update_plan
[
{"id": "1", "title": "Создать класс Equation", "status": "pending"},
{"id": "2", "title": "Создать ICalcMode", "status": "active"}
]
TASK_COMPLETED"""
    cleaned, calls = parse_text_tool_calls(raw, ["update_plan"])
    assert len(calls) == 1
    assert calls[0].arguments["items"][0]["id"] == "1"
    assert calls[0].arguments["items"][1]["status"] == "active"
    assert "TASK_COMPLETED" in cleaned
    assert "update_plan" not in cleaned


def test_channel_calls_are_the_model_template():
    from Kerniq.models.text_tools import extract_channel_tool_calls

    qwen = (
        "Writing the file.\n"
        '<tool_call>{"name":"write_file","arguments":{"path":"a","content":"b"}}</tool_call>'
    )
    cleaned, calls = extract_channel_tool_calls(qwen)
    assert len(calls) == 1
    assert calls[0].name == "write_file"
    assert calls[0].arguments == {"path": "a", "content": "b"}
    assert "<tool_call>" not in cleaned
    assert "Writing the file." in cleaned

    boxed = '[TOOL_REQUEST]{"name": "read_file", "arguments": {"path": "src/a.py"}}[END_TOOL_REQUEST]'
    cleaned, calls = extract_channel_tool_calls(boxed)
    assert calls[0].name == "read_file"
    assert calls[0].arguments["path"] == "src/a.py"
    assert cleaned == ""

    gemma = (
        '<|tool_call>call:write_file{path:<|"|>CalculatorCore/IMathOperation.cs<|"|>,'
        'content:<|"|>public class X { int y; }<|"|>,replace_all:true}<tool_call|>'
    )
    cleaned, calls = extract_channel_tool_calls(gemma)
    assert len(calls) == 1
    assert calls[0].name == "write_file"
    assert calls[0].arguments["path"] == "CalculatorCore/IMathOperation.cs"
    assert calls[0].arguments["content"] == "public class X { int y; }"
    assert calls[0].arguments["replace_all"] is True
    assert "write_file" not in cleaned
    assert '<|"|>' not in cleaned


def test_empty_reply_still_sends_native_tools():
    import asyncio
    from types import SimpleNamespace
    from uuid import uuid4

    from Kerniq.core.context import TaskContext
    from Kerniq.core.orchestrator import Orchestrator
    from Kerniq.interfaces.models import Message, MessageRole, ModelResponse

    class Prov:
        model = "google/gemma-4-e2b"

        def __init__(self):
            self.seen = []

        async def generate(self, request):
            self.seen.append(request.tools)
            if len(self.seen) == 1:
                return ModelResponse(messages=[], finish_reason="stop")
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="Done. TASK_COMPLETED")],
                finish_reason="stop",
            )

    prov = Prov()
    orch = Orchestrator(
        prov,
        SimpleNamespace(
            get_tools_for_model=lambda: [{"type": "function", "function": {"name": "read_file"}}],
            list_tools=lambda: [],
        ),
    )
    orch.compose_plan = False
    orch.max_iterations = 4
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="read")
    ctx.add_message(Message(role=MessageRole.USER, content="read the file"))
    asyncio.run(orch.run(ctx))
    assert len(prov.seen) >= 2
    assert prov.seen[0] and prov.seen[1]
    assert "google/gemma-4-e2b" not in orch._text_only_models
    assert orch._model_needs_text_tools("google/gemma-4-e2b") is False


def test_one_written_call_does_not_disable_native_tools():
    from types import SimpleNamespace

    from Kerniq.core.orchestrator import Orchestrator
    from Kerniq.interfaces.models import Message, MessageRole, ModelResponse

    class Registry:
        def list_tools(self):
            return [SimpleNamespace(name="update_plan")]

    orch = Orchestrator(provider=None, tool_registry=Registry())
    response = ModelResponse(
        finish_reason="stop",
        messages=[
            Message(
                role=MessageRole.ASSISTANT,
                content="",
                metadata={"reasoning": 'update_plan\n[{"id": "1", "title": "Сделать", "status": "pending"}]'},
            )
        ],
    )
    assert orch._absorb_text_tool_calls(response, "google/gemma-4-e2b") is True
    assert response.messages[0].tool_calls[0].name == "update_plan"
    assert response.messages[0].content == ""
    assert "google/gemma-4-e2b" not in orch._text_only_models


def test_auto_load_leaves_a_working_model_alone():
    from Kerniq.models.load_policy import resolve_auto_load

    busy = plan_model_load("google/gemma-4-e2b", ["google/gemma-4-12b"], busy=True)
    idle = plan_model_load("google/gemma-4-e2b", ["google/gemma-4-12b"], busy=False)
    assert resolve_auto_load(busy, "notify") == "notify"
    assert resolve_auto_load(idle, "notify") == "notify"
    assert resolve_auto_load(busy, "unload_idle") == "alongside"
    assert resolve_auto_load(idle, "unload_idle") == "unload"
    assert resolve_auto_load(busy, "unload_busy") == "unload_busy"
    assert resolve_auto_load(busy, "alongside") == "alongside"
    ready = plan_model_load(
        instance_model_key("google/gemma-4-e2b"),
        [instance_model_key("google/gemma-4-e2b:2")],
    )
    assert ready.status == "ready"
    assert resolve_auto_load(ready, "notify") == "alongside"


def test_native_tool_flag_is_remembered(tmp_path):
    assert native_tools_enabled(tmp_path, "google/gemma-4-e2b") is True
    remember_native_tools(tmp_path, "google/gemma-4-e2b", False)
    assert native_tools_enabled(tmp_path, "google/gemma-4-e2b") is False
    assert native_tools_enabled(tmp_path, "google/gemma-4-12b") is True


def test_api_token_is_not_plaintext_on_disk(tmp_path):
    store = UiSettingsStore(tmp_path)
    settings = store.load()
    settings.api.api_token = "sk-secret"
    store.save(settings)
    raw = (tmp_path / "settings.json").read_text(encoding="utf-8")
    assert "sk-secret" not in raw
    assert token_is_plaintext({"api": {"api_token": "sk-secret"}})
    fresh = UiSettingsStore(tmp_path)
    assert fresh.load().api.api_token == "sk-secret"
