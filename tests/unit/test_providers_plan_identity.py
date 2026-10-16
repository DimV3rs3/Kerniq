"""Provider catalog, identity prompt, plan tool, and context outlines."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from Kerniq.core.agent import KERNIQ_IDENTITY, PLAN_MODE_TEXT, compose_system_prompt
from Kerniq.core.context import TaskContext
from Kerniq.core.orchestrator import Orchestrator
from Kerniq.interfaces.models import Message, MessageRole, ModelResponse
from Kerniq.models.catalog import spec_by_id
from Kerniq.models.factory import build_provider
from Kerniq.tools.packs.plan.tools import UpdatePlanTool


def test_cli_does_not_hardcode_tool_imports():
    root = Path(__file__).resolve().parents[2]
    text = (root / "src/Kerniq/interfaces_runtime/cli/main.py").read_text(encoding="utf-8")
    assert "FileSystemTools" not in text
    assert "WebSearchTool" not in text
    assert "FetchUrlTool" not in text
    assert "build_tool_registry" in text
    ui = (root / "plugins/web_ui/main.py").read_text(encoding="utf-8")
    tools_fn = ui.split("def _tools", 1)[1].split("def _plugins", 1)[0]
    assert "load_all_tools" in tools_fn
    assert "list_directory" not in tools_fn


def test_identity_is_before_the_operator_prompt():
    text = compose_system_prompt("OPERATOR RULE: prefer tiny diffs.", lang="ru", mode="plan")
    assert text.startswith(KERNIQ_IDENTITY)
    assert text.index(KERNIQ_IDENTITY) < text.index("OPERATOR RULE")
    assert "нескольк" in text or "several project files" in text
    assert PLAN_MODE_TEXT in text
    assert "Russian" in text


def test_deepseek_ui_is_key_and_model_only():
    spec = spec_by_id("deepseek")
    assert [f["key"] for f in spec["fields"]] == ["api_token", "model"]


def test_claude_code_is_a_path_not_a_key():
    spec = spec_by_id("claude_code")
    keys = [f["key"] for f in spec["fields"]]
    assert keys == ["binary_path", "model"]
    assert spec["tool_calls"] is False


def test_known_remote_providers_exist():
    for pid in ("openrouter", "openai", "anthropic", "gemini", "groq", "mistral", "ollama"):
        assert spec_by_id(pid) is not None


def test_deepseek_ignores_stale_local_base_url():
    api = SimpleNamespace(
        model_dump=lambda: {
            "provider": "deepseek",
            "base_url": "http://127.0.0.1:1234",
            "api_token": "sk-test",
            "model": "deepseek-chat",
            "binary_path": "",
        }
    )
    provider = build_provider("deepseek", api=api)
    assert "deepseek.com" in provider.base_url
    assert "127.0.0.1" not in provider.base_url


def test_mock_provider_builds():
    provider = build_provider("mock")
    assert provider.provider_id == "mock_provider"


def test_update_plan_tool():
    tool = UpdatePlanTool()
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="ship it")
    result = asyncio.run(
        tool.execute(
            {
                "items": [
                    {"id": "a", "title": "Read parser", "status": "done"},
                    {"id": "b", "title": "Edit parser", "status": "in_progress"},
                ]
            },
            ctx,
        )
    )
    assert result.success
    assert ctx.metadata["plan"][0]["status"] == "done"
    assert ctx.metadata["plan"][1]["status"] == "active"


def test_plan_inserts_only_from_the_active_item_down():
    from Kerniq.tools.packs.plan.tools import merge_plan

    prior = [
        {"id": "1", "title": "one", "status": "done"},
        {"id": "2", "title": "two", "status": "done"},
        {"id": "3", "title": "three", "status": "done"},
        {"id": "4", "title": "four", "status": "active"},
        {"id": "5", "title": "five", "status": "pending"},
        {"id": "6", "title": "six", "status": "pending"},
        {"id": "7", "title": "seven", "status": "pending"},
    ]
    incoming = [
        {"id": "1", "title": "one", "status": "done"},
        {"id": "2", "title": "two", "status": "done"},
        {"id": "new-early", "title": "should move down", "status": "pending"},
        {"id": "3", "title": "renamed", "status": "done"},
        {"id": "4", "title": "renamed too", "status": "active"},
        {"id": "5", "title": "five", "status": "pending"},
        {"id": "new-mid", "title": "between five and six", "status": "pending"},
        {"id": "6", "title": "six", "status": "frozen"},
        {"id": "7", "title": "seven", "status": "failed"},
    ]
    out = merge_plan(prior, incoming)
    assert [item["id"] for item in out] == ["1", "2", "3", "4", "new-early", "5", "new-mid", "6", "7"]
    assert out[3]["title"] == "four"
    assert out[2]["title"] == "three"
    assert out[3]["status"] == "active"
    assert out[7]["status"] == "pending"
    assert out[8]["status"] == "pending"
    assert sum(1 for item in out if item["status"] == "active") == 1


def test_plan_cannot_delete_or_run_two_items():
    from Kerniq.tools.packs.plan.tools import merge_plan

    prior = [
        {"id": "1", "title": "one", "status": "done"},
        {"id": "2", "title": "two", "status": "active"},
        {"id": "3", "title": "three", "status": "pending"},
        {"id": "4", "title": "four", "status": "pending"},
    ]
    wiped = merge_plan(prior, [])
    assert [item["id"] for item in wiped] == ["1", "2", "3", "4"]
    assert wiped[0]["status"] == "done"
    assert wiped[1]["status"] == "active"
    skipped = merge_plan(
        prior,
        [
            {"id": "2", "title": "renamed", "status": "active"},
            {"id": "3", "title": "three", "status": "done"},
            {"id": "4", "title": "four", "status": "active"},
        ],
    )
    assert [item["title"] for item in skipped] == ["one", "two", "three", "four"]
    assert [item["status"] for item in skipped] == ["done", "active", "pending", "pending"]
    advanced = merge_plan(
        prior,
        [
            {"id": "1", "title": "one", "status": "done"},
            {"id": "2", "title": "two", "status": "done"},
            {"id": "3", "title": "three", "status": "failed"},
            {"id": "4", "title": "four", "status": "active"},
        ],
    )
    assert [item["status"] for item in advanced] == ["done", "done", "active", "pending"]


def test_frozen_and_failed_block_finish():
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="act")
    ctx.metadata["agent_mode"] = "act"
    orch = Orchestrator(provider=None, tool_registry=None)
    orch.finish_open_plan = True
    ctx.metadata["plan"] = [{"id": "a", "title": "hold", "status": "frozen"}]
    assert orch._continue_open_plan(ctx, 3) is True
    ctx.metadata["plan"] = [{"id": "a", "title": "boom", "status": "failed"}]
    assert orch._continue_open_plan(ctx, 3) is True
    ctx.metadata["plan"] = [{"id": "a", "title": "ok", "status": "done"}]
    ctx.metadata["plan_archive"] = [{"id": "a", "title": "ok", "status": "done"}]
    assert orch._continue_open_plan(ctx, 3) is False


def test_compaction_does_not_spend_an_iteration():
    from Kerniq.interfaces.models import ModelRequest

    calls = {"n": 0}

    class Prov:
        async def generate(self, request: ModelRequest):
            calls["n"] += 1
            if (request.metadata or {}).get("kerniq_internal") == "compact":
                return ModelResponse(
                    messages=[Message(role=MessageRole.ASSISTANT, content="summary of files and TODO")],
                    finish_reason="stop",
                )
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="The script is written.")],
                finish_reason="stop",
            )

    class Comp:
        cfg_enabled = True
        last_summary = ""

        def needs_compact(self, messages):
            return not self.last_summary

        async def summarize(self, messages, provider):
            response = await provider.generate(
                ModelRequest(
                    messages=messages[:1],
                    session_id=uuid4(),
                    tools=None,
                    metadata={"kerniq_internal": "compact"},
                )
            )
            self.last_summary = response.messages[0].content
            return self.last_summary

        def compact(self, messages, summary):
            return messages

    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="write a script")
    ctx.metadata["agent_mode"] = "act"
    ctx.add_message(Message(role=MessageRole.SYSTEM, content="system"))
    ctx.add_message(Message(role=MessageRole.USER, content="write a script"))
    orch = Orchestrator(Prov(), tool_registry=SimpleNamespace(get_tools_for_model=lambda: [], list_tools=lambda: []))
    orch.max_iterations = 1
    orch.compactor = Comp()
    orch.finish_open_plan = False
    result = asyncio.run(orch.run(ctx))
    assert calls["n"] == 2
    assert ctx.metadata.get("iterations_used") == 1
    assert "script" in result
    assert ctx.metadata.get("outcome") != "max_iterations"


def test_plan_mode_blocks_writes():
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="plan")
    ctx.metadata["agent_mode"] = "plan"
    write = SimpleNamespace(name="write_file", risk_level="medium")
    read = SimpleNamespace(name="read_file", risk_level="low")
    plan = SimpleNamespace(name="update_plan", risk_level="read_only")
    assert Orchestrator.plan_blocks_tool(ctx, write) is True
    assert Orchestrator.plan_blocks_tool(ctx, read) is False
    assert Orchestrator.plan_blocks_tool(ctx, plan) is False
    ctx.metadata["agent_mode"] = "act"
    assert Orchestrator.plan_blocks_tool(ctx, write) is False


def test_compact_outlines_symbols_not_bodies():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    spec = importlib.util.spec_from_file_location("context_compact_outline", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.PluginImpl()
    plugin.cfg_keep_last = 1
    body = "def parse_tokens(src):\n" + ("    x = 1\n" * 80) + "class Parser:\n    pass\n"
    messages = [
        Message(role=MessageRole.SYSTEM, content="system"),
        Message(role=MessageRole.USER, content="fix parser.py"),
        Message(role=MessageRole.ASSISTANT, content="working on src/parser.py\n" + body),
        Message(role=MessageRole.USER, content="go on"),
        Message(role=MessageRole.ASSISTANT, content="tail"),
    ]
    out = plugin.compact(messages)
    blob = "\n".join(m.content for m in out)
    assert "parse_tokens" in blob
    assert "Parser" in blob
    assert "src/parser.py" in blob
    assert "x = 1" not in blob
    assert "fix parser.py" in blob
    assert any(m.content == "tail" for m in out)


def test_summarize_sends_outline_not_source():
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    spec = importlib.util.spec_from_file_location("context_compact_sum", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.PluginImpl()
    plugin.cfg_keep_last = 1
    body = "class Invoice:\n    def total(self):\n" + ("        return 1\n" * 40)
    messages = [
        Message(role=MessageRole.SYSTEM, content="system"),
        Message(role=MessageRole.USER, content="audit billing"),
        Message(role=MessageRole.ASSISTANT, content="file src/billing.py\n" + body),
        Message(role=MessageRole.USER, content="continue"),
        Message(role=MessageRole.ASSISTANT, content="kept"),
    ]
    seen = {}

    class Fake:
        async def generate(self, request):
            seen["system"] = request.messages[0].content
            seen["user"] = request.messages[1].content
            seen["internal"] = (request.metadata or {}).get("kerniq_internal")
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="Files: src/billing.py symbols: Invoice.total")],
                finish_reason="stop",
            )

    text = asyncio.run(plugin.summarize(messages, Fake()))
    assert "class names" in seen["system"] or "method" in seen["system"]
    assert "Invoice" in seen["user"]
    assert "return 1" not in seen["user"]
    assert seen["internal"] == "compact"
    assert "billing.py" in text


def test_chat_payload_keeps_a_single_leading_system_message():
    from Kerniq.models.providers.openai_compat import to_openai_messages
    from Kerniq.models.providers.lm_studio import LMStudioProvider

    messages = [
        Message(role=MessageRole.SYSTEM, content="You are Kerniq."),
        Message(role=MessageRole.SYSTEM, content="[Pinned TODO. keep the checklist]"),
        Message(role=MessageRole.USER, content="audit the workspace"),
        Message(role=MessageRole.ASSISTANT, content="looking"),
    ]
    rows = to_openai_messages(messages)
    assert [row["role"] for row in rows] == ["system", "user", "assistant"]
    assert rows[0]["content"].startswith("You are Kerniq.")
    assert "[Pinned TODO." in rows[0]["content"]
    same = LMStudioProvider(base_url="http://127.0.0.1:1234")._to_openai_messages(messages)
    assert [row["role"] for row in same] == ["system", "user", "assistant"]
    assert same[0]["content"] == rows[0]["content"]


def test_numeric_plan_ids_are_sorted():
    from Kerniq.tools.packs.plan.tools import merge_plan
    scrambled = [
        {"id": "1", "title": "a", "status": "pending"},
        {"id": "2", "title": "b", "status": "pending"},
        {"id": "9", "title": "i", "status": "pending"},
        {"id": "7", "title": "g", "status": "pending"},
        {"id": "6", "title": "f", "status": "pending"},
        {"id": "5", "title": "e", "status": "pending"},
        {"id": "3", "title": "c", "status": "pending"},
        {"id": "8", "title": "h", "status": "pending"},
        {"id": "4", "title": "d", "status": "pending"},
    ]
    ordered = merge_plan([], scrambled)
    assert [item["id"] for item in ordered] == ["1", "2", "3", "4", "5", "6", "7", "8", "9"]


def test_compact_budget_uses_half_the_window_not_1200():
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    spec = importlib.util.spec_from_file_location("context_compact_budget", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.PluginImpl()
    plugin.cfg_context_limit = 262144
    plugin.cfg_trigger_percent = 75
    plugin.cfg_target_percent = 50
    plugin.cfg_target_mode = "percent"
    assert plugin.trigger_tokens() == int(262144 * 75 / 100)
    assert plugin.target_tokens() == int(262144 * 50 / 100)
    assert plugin.summary_token_budget(20_000) > 1200
    short = [Message(role=MessageRole.USER, content="x" * (20_000 * 4))]
    assert plugin.needs_compact(short) is False
    plugin.cfg_context_limit = 0
    assert plugin.needs_compact(short) is False
