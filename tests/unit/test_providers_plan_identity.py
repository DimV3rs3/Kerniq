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
