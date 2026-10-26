"""Benchmark plugin contract, MCP publish filter, sandbox location, plan close-out."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

from Kerniq.core.context import TaskContext
from Kerniq.core.orchestrator import Orchestrator
from Kerniq.interfaces.models import Message, MessageRole, ModelResponse
from Kerniq.interfaces.settings_schema import SettingType
from Kerniq.mcp.publish import resolve_published_names
from Kerniq.sandbox.venv import sandbox_workspace
from Kerniq.security.policy import PolicyDecision, RiskLevel


def test_benchmark_plugin_schema_validates():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "plugins" / "benchmark_pro" / "main.py"
    spec = importlib.util.spec_from_file_location("benchmark_pro_main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    plugin = mod.PluginImpl()
    assert plugin.manifest is not None
    assert plugin.manifest.plugin_id == "benchmark_pro"
    schema = plugin.settings_schema()
    assert all(isinstance(field.type, SettingType) for field in schema.fields)
    slots = mod.slots_from({"task": "one", "system_2": "be brief", "task_2": "two", "task_3": ""})
    assert len(slots) == 2
    assert slots[0]["task"] == "one"
    assert slots[1]["system"] == "be brief"


def test_results_dir_stays_inside_the_workspace(tmp_path):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "plugins" / "benchmark_pro" / "main.py"
    spec = importlib.util.spec_from_file_location("benchmark_pro_paths", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    default = mod.results_dir(tmp_path, "")
    assert default == (tmp_path / "benchmarks").resolve()
    nested = mod.results_dir(tmp_path, "benchmarks/custom")
    assert nested == (tmp_path / "benchmarks" / "custom").resolve()
    try:
        mod.results_dir(tmp_path, "..")
    except ValueError:
        pass
    else:
        raise AssertionError("a path outside the workspace must be refused")


def test_sandbox_refuses_the_install_tree(tmp_path):
    project = tmp_path / "Kerniq"
    (project / "src" / "Kerniq").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (project / "workspace").mkdir()
    assert sandbox_workspace(project) is None
    assert sandbox_workspace(project / "src") is None
    assert sandbox_workspace(project / "workspace") == (project / "workspace").resolve()
    assert sandbox_workspace(tmp_path / "other") == (tmp_path / "other").resolve()


def test_mcp_hides_plan_and_plugin_commands():
    tools = [
        SimpleNamespace(name="read_file", risk_level="low"),
        SimpleNamespace(name="update_plan", risk_level="read_only"),
        SimpleNamespace(name="plugin_search", risk_level="low", agent_visible=False),
        SimpleNamespace(name="plugin_install", risk_level="high"),
    ]

    class Reg:
        def list_tools(self):
            return tools

    class Policy:
        def resolve_risk(self, name, declared, tool):
            return RiskLevel.LOW

        def evaluate_tool_call(self, name, arguments, declared, tool=None):
            return PolicyDecision.ALLOW

    names = resolve_published_names(Reg(), Policy(), None)
    assert names == ["read_file"]
    explicit = resolve_published_names(Reg(), Policy(), ["read_file", "update_plan", "plugin_search"])
    assert explicit == ["read_file"]


def test_declared_completion_fails_every_open_item():
    class Prov:
        async def generate(self, request):
            return ModelResponse(
                messages=[Message(
                    role=MessageRole.ASSISTANT,
                    content="The work is complete. TASK_COMPLETED",
                )],
                finish_reason="stop",
            )

    orch = Orchestrator(
        Prov(),
        SimpleNamespace(get_tools_for_model=lambda: [], list_tools=lambda: []),
    )
    orch.compose_plan = False
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="do it")
    ctx.metadata["agent_mode"] = "act"
    ctx.metadata["plan"] = [
        {"id": "1", "title": "one", "status": "done"},
        {"id": "2", "title": "two", "status": "active"},
        {"id": "3", "title": "three", "status": "pending"},
    ]
    ctx.add_message(Message(role=MessageRole.USER, content="do it"))
    result = asyncio.run(orch.run(ctx))
    assert "complete" in result.lower()
    assert [item["status"] for item in ctx.metadata["plan"]] == ["done", "failed", "failed"]
    assert ctx.metadata.get("outcome") not in ("no_plan", "max_iterations")


def test_rank_puts_a_failed_load_behind_a_finished_run():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "plugins" / "benchmark_pro" / "main.py"
    spec = importlib.util.spec_from_file_location("benchmark_pro_rank", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ranked = mod.rank_rows([
        {"model": "good", "status": "ok", "seconds": 10, "iterations": 2, "tool_calls": 3, "tool_errors": 0, "file_count": 2},
        {"model": "bad", "status": "load_failed", "seconds": 1, "iterations": 0, "tool_calls": 0, "tool_errors": 0, "file_count": 0, "load_seconds": 1},
    ])
    assert [row["model"] for row in ranked] == ["good", "bad"]
    assert ranked[0]["rank"] == 1
    assert ranked[0]["score"] > ranked[1]["score"]
    packet = mod.anonymous_packet(
        [{"model": "secret-model", "slot": 1, "status": "ok", "answer": "hello", "seconds": 1}],
        ["secret-model"],
        ranked[:1] if False else mod.rank_rows([
            {"model": "secret-model", "status": "ok", "seconds": 1, "iterations": 1, "tool_calls": 0, "tool_errors": 0, "file_count": 1},
        ]),
    )
    assert "secret-model" not in packet
    assert "Output A" in packet
    assert "rank 1" in packet


def test_compose_plan_requires_an_enabled_plan_tool():
    from Kerniq.core.runtime_flow import compose_plan_allowed

    assert compose_plan_allowed(None) is False

    class Missing:
        def list_tools(self):
            return [SimpleNamespace(name="read_file", include_in_plan=True, agent_visible=True)]

    class Disabled:
        def list_tools(self):
            return [SimpleNamespace(name="update_plan", include_in_plan=False, agent_visible=True)]

    class Ready:
        def list_tools(self):
            return [SimpleNamespace(name="update_plan", include_in_plan=True, agent_visible=True)]

    assert compose_plan_allowed(Missing()) is False
    assert compose_plan_allowed(Disabled()) is False
    assert compose_plan_allowed(Ready()) is True


def test_internal_note_is_not_a_user_message():
    class Prov:
        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            if self.calls == 1:
                return ModelResponse(messages=[], finish_reason="stop")
            return ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="done")],
                finish_reason="stop",
            )

    orch = Orchestrator(Prov(), SimpleNamespace(get_tools_for_model=lambda: [], list_tools=lambda: []))
    orch.compose_plan = False
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="look")
    ctx.add_message(Message(role=MessageRole.USER, content="look"))
    asyncio.run(orch.run(ctx))
    users = [m.content for m in ctx.messages if m.role == MessageRole.USER]
    assert users == ["look"]
    system = ctx.messages[0].content
    assert "[Kerniq note]" in system or ctx.metadata.get("outcome") == "success" or "done" in system


def _benchmark_module(name: str):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "plugins" / "benchmark_pro" / "main.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_catalog_order_trim_and_final_analyzer():
    import random

    mod = _benchmark_module("benchmark_pro_select")
    rows = []
    for index, (weight, context) in enumerate((
        (1, 2048), (1, 8192), (2, 4096), (3, 4096), (4, 8192),
        (5, 8192), (6, 8192), (7, 16384), (8, 16384), (9, 32000), (10, 128000),
    )):
        rows.append({
            "id": f"m{index:02d}",
            "name": f"m{index:02d}",
            "weight_bytes": weight * 1_000_000_000,
            "max_context_length": context,
        })
    ordered = mod.prepare_models(rows)
    assert [row["id"] for row in ordered] == [f"m{index:02d}" for index in range(11)]
    pool = mod.trim_edges(ordered, 0.1)
    assert [row["id"] for row in pool] == [f"m{index:02d}" for index in range(1, 10)]
    assert mod.final_analyzer(ordered)["id"] == "m10"
    tied = mod.prepare_models([
        {"id": "light-ctx", "name": "b", "weight_bytes": 5, "max_context_length": 1000},
        {"id": "wide-ctx", "name": "a", "weight_bytes": 5, "max_context_length": 4000},
    ])
    assert [row["id"] for row in tied] == ["light-ctx", "wide-ctx"]
    assert mod.final_analyzer(tied)["id"] == "wide-ctx"
    named = mod.prepare_models([
        {"id": "publisher/model-70b-q4", "name": "Big"},
        {"id": "publisher/model-7b-q4", "name": "Small"},
        {"id": "publisher/embed-small", "name": "Embed", "type": "embedding"},
    ])
    assert [row["id"] for row in named] == ["publisher/model-7b-q4", "publisher/model-70b-q4"]
    assert named[-1]["weight"] > named[0]["weight"]
    counts = [mod.gaussian_count(8, random.Random(seed)) for seed in range(400)]
    assert min(counts) >= 0 and max(counts) <= 8
    assert 3.0 < (sum(counts) / len(counts)) < 6.5
    try:
        mod.provider_id_from(None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("an empty provider must not fall back to mock")
    assert mod.provider_id_from(SimpleNamespace(provider="lm_studio")) == "lm_studio"
    keys = [field.key for field in mod.PluginImpl().settings_schema().fields]
    assert "max_iterations" not in keys
    assert "timeout_seconds" not in keys
    assert "analyzer_count" not in keys

