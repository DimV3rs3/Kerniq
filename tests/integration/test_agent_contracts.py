"""Critical agent-loop contracts using MockProvider. No live LM Studio."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from Kerniq.core.agent import Agent
from Kerniq.core.orchestrator import Orchestrator
from Kerniq.core.context import TaskContext
from Kerniq.interfaces.errors import ErrorCode, ProviderError
from Kerniq.interfaces.models import (
    GenerationOptions,
    Message,
    MessageRole,
    ModelRequest,
    ModelResponse,
    ToolCall,
)
from Kerniq.interfaces.tools import Tool, ToolResult
from Kerniq.models.providers.mock import MockProvider
from Kerniq.security.policy import SecurityPolicy
from Kerniq.tools.filesystem import FileSystemTools
from Kerniq.tools.registry import ToolRegistry


def _msg(content="", tool_calls=None):
    return ModelResponse(
        messages=[
            Message(
                role=MessageRole.ASSISTANT,
                content=content,
                tool_calls=tool_calls,
            )
        ],
        finish_reason="tool_calls" if tool_calls else "stop",
    )


def _call(name, arguments, call_id="c1"):
    return ToolCall(id=call_id, name=name, arguments=arguments)


class _Boom(Tool):
    @property
    def tool_id(self):
        return "boom"

    @property
    def name(self):
        return "boom"

    @property
    def description(self):
        return "Always fails."

    @property
    def input_schema(self):
        return {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}

    @property
    def risk_level(self):
        return "low"

    async def execute(self, arguments, context):
        raise RuntimeError("boom failed")


class _Counter(Tool):
    def __init__(self):
        self.calls = 0

    @property
    def tool_id(self):
        return "counter"

    @property
    def name(self):
        return "counter"

    @property
    def description(self):
        return "Counts calls."

    @property
    def input_schema(self):
        return {"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}

    @property
    def risk_level(self):
        return "low"

    async def execute(self, arguments, context):
        self.calls += 1
        return ToolResult(
            tool_call_id="x",
            tool_id=self.tool_id,
            status="success",
            output={"n": self.calls},
            human_readable=str(self.calls),
        )


def _run(coro):
    return asyncio.run(coro)


def test_modules_import():
    import Kerniq.app
    import Kerniq.bootstrap
    import Kerniq.core.agent
    import Kerniq.core.orchestrator
    import Kerniq.models.router
    import Kerniq.models.providers.lm_studio
    import Kerniq.models.system_info
    import Kerniq.mcp.server
    import Kerniq.sessions.manager
    import Kerniq.interfaces_runtime.cli.main

    assert Kerniq.app.Application
    assert Kerniq.models.router.ModelRouter


def test_application_registers_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        "\n".join(
            [
                "[application]",
                'workspace_root = "./ws"',
                "auto_install_deps = false",
                "[models]",
                'default_provider = "mock"',
                "[security]",
                "require_approval_for_high_risk = true",
                "[tools]",
                "fs_enabled = true",
                "terminal_enabled = true",
                "web_search_enabled = false",
                "fetch_url_enabled = false",
            ]
        ),
        encoding="utf-8",
    )
    from Kerniq.app import Application

    app = Application(cfg)
    names = {t.name for t in app.tool_registry.list_tools()}
    assert "read_file" in names
    assert "run_command" in names
    assert app.get_provider("mock").provider_id == "mock_provider"


def test_mock_task_and_single_tool(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "hello.txt").write_text("Hello World", encoding="utf-8")
    registry = ToolRegistry()
    for tool in FileSystemTools(str(workspace)).get_tools():
        registry.register_tool(tool)
    provider = MockProvider(
        [
            _msg("reading", [_call("read_file", {"path": "hello.txt"})]),
            _msg("The file contains: Hello World"),
        ]
    )
    agent = Agent(provider, registry)

    async def go():
        return await agent.run("read hello", workspace=str(workspace))

    result = _run(go())
    assert "Hello World" in result
    assert "outcome=unverified" in result
    assert agent.last_context.metadata["outcome"] == "unverified"


def test_multiple_tool_calls_one_turn(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "a.txt").write_text("AAA", encoding="utf-8")
    (workspace / "b.txt").write_text("BBB", encoding="utf-8")
    registry = ToolRegistry()
    for tool in FileSystemTools(str(workspace)).get_tools():
        registry.register_tool(tool)
    provider = MockProvider(
        [
            _msg(
                "both",
                [
                    _call("read_file", {"path": "a.txt"}, "1"),
                    _call("read_file", {"path": "b.txt"}, "2"),
                ],
            ),
            _msg("Got AAA and BBB"),
        ]
    )
    agent = Agent(provider, registry)
    result = _run(agent.run("read both", workspace=str(workspace)))
    assert "AAA" in result and "BBB" in result
    roles = [m.role for m in agent.last_context.messages]
    assert roles.count(MessageRole.TOOL) == 2


def test_sequential_cycles_and_tool_error(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = ToolRegistry()
    for tool in FileSystemTools(str(workspace)).get_tools():
        registry.register_tool(tool)
    boom = _Boom()
    registry.register_tool(boom)
    provider = MockProvider(
        [
            _msg("", [_call("boom", {"path": "x"}, "b1")]),
            _msg("", [_call("write_file", {"path": "out.txt", "content": "ok"}, "w1")]),
            _msg("wrote out.txt"),
        ]
    )
    agent = Agent(provider, registry)
    result = _run(agent.run("write", workspace=str(workspace)))
    assert (workspace / "out.txt").read_text(encoding="utf-8") == "ok"
    tool_msgs = [m.content for m in agent.last_context.messages if m.role == MessageRole.TOOL]
    assert any("boom failed" in c or "success" in c and "false" in c.lower() for c in tool_msgs)
    assert "wrote out.txt" in result


def test_invalid_arguments_do_not_run(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    registry = ToolRegistry()
    for tool in FileSystemTools(str(workspace)).get_tools():
        registry.register_tool(tool)
    provider = MockProvider(
        [
            _msg("", [_call("read_file", {}, "bad")]),
            _msg("could not read"),
        ]
    )
    agent = Agent(provider, registry)
    result = _run(agent.run("read", workspace=str(workspace)))
    blob = "\n".join(m.content for m in agent.last_context.messages)
    assert "missing required argument" in blob
    assert "could not read" in result


def test_provider_retry_then_success():
    class Flaky(MockProvider):
        def __init__(self):
            super().__init__([_msg("recovered")])
            self.attempts = 0

        async def generate(self, request):
            self.attempts += 1
            if self.attempts == 1:
                raise ProviderError(ErrorCode.PROVIDER_UNAVAILABLE, "connection reset by peer")
            return await super().generate(request)

    provider = Flaky()
    agent = Agent(provider, ToolRegistry())
    agent.orchestrator.provider_retries = 2
    result = _run(agent.run("hi"))
    assert "recovered" in result
    assert provider.attempts == 2


def test_provider_timeout_stops():
    class Down(MockProvider):
        def __init__(self):
            super().__init__([])
            self.attempts = 0

        async def generate(self, request):
            self.attempts += 1
            raise ProviderError(ErrorCode.PROVIDER_REQUEST_FAILED, "LM Studio chat timeout after 1s")

    provider = Down()
    agent = Agent(provider, ToolRegistry())
    agent.orchestrator.provider_retries = 1
    result = _run(agent.run("hi"))
    assert agent.last_context.metadata["outcome"] == "provider_error"
    assert "timeout" in result
    assert provider.attempts == 2


def test_empty_then_answer_and_bad_payload():
    provider = MockProvider(
        [
            ModelResponse(messages=[Message(role=MessageRole.ASSISTANT, content="")], finish_reason="stop"),
            _msg("final answer here"),
        ]
    )
    agent = Agent(provider, ToolRegistry())
    result = _run(agent.run("say something"))
    assert "final answer here" in result

    class Bad:
        provider_id = "bad"

        async def generate(self, request):
            return {"not": "a response"}

        async def check_connection(self):
            return True

        def get_capabilities(self):
            return {}

    agent = Agent(Bad(), ToolRegistry())
    result = _run(agent.run("x"))
    assert agent.last_context.metadata["outcome"] == "provider_error"


def test_repeat_detection_changes_course():
    counter = _Counter()
    registry = ToolRegistry()
    registry.register_tool(counter)
    provider = MockProvider(
        [
            _msg("", [_call("counter", {"n": 1}, "a")]),
            _msg("", [_call("counter", {"n": 1}, "b")]),
            _msg("", [_call("counter", {"n": 1}, "c")]),
            _msg("stopped repeating"),
        ]
    )
    agent = Agent(provider, registry)
    result = _run(agent.run("count"))
    assert counter.calls == 2
    assert "stopped repeating" in result
    assert any("Skipped: this exact tool call" in m.content for m in agent.last_context.messages)


def test_context_keeps_goal_and_compacts(tmp_path):
    registry = ToolRegistry()
    agent = Agent(MockProvider([_msg("done")]), registry)
    orch = agent.orchestrator
    from Kerniq.interfaces.models import Message as Msg

    messages = [Msg(role=MessageRole.SYSTEM, content="system rules " * 20)]
    messages.append(Msg(role=MessageRole.USER, content="ORIGINAL_GOAL keep me"))
    for i in range(30):
        messages.append(Msg(role=MessageRole.ASSISTANT, content=f"note {i} " + ("x" * 80)))
        messages.append(Msg(role=MessageRole.USER, content=f"follow {i} " + ("y" * 80)))
    trimmed = orch._trim_messages_to_budget(messages, 80)
    blob = "\n".join(m.content for m in trimmed)
    assert "ORIGINAL_GOAL keep me" in blob
    assert any(m.role == MessageRole.SYSTEM and m.content.startswith("system rules") for m in trimmed)

    from importlib.machinery import SourceFileLoader

    plug_path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    mod = SourceFileLoader("ctx_compact_test", str(plug_path)).load_module()
    comp = mod.PluginImpl()
    comp.cfg_keep_last = 4
    comp.cfg_max_tokens = 100
    comp.cfg_trigger_percent = 1
    long_msgs = [Msg(role=MessageRole.SYSTEM, content="sys")]
    long_msgs.append(Msg(role=MessageRole.USER, content="GOAL_TOKEN"))
    long_msgs.append(
        Msg(
            role=MessageRole.ASSISTANT,
            content="call",
            tool_calls=[_call("read_file", {"path": "a"}, "t1")],
        )
    )
    long_msgs.append(Msg(role=MessageRole.TOOL, content="FILE_BODY", tool_call_id="t1", name="read_file"))
    for i in range(10):
        long_msgs.append(Msg(role=MessageRole.USER, content=f"u{i} " + "z" * 50))
        long_msgs.append(Msg(role=MessageRole.ASSISTANT, content=f"a{i} " + "z" * 50))
    assert comp.needs_compact(long_msgs)
    compacted = comp.compact(long_msgs)
    text = "\n".join(m.content or "" for m in compacted)
    assert "GOAL_TOKEN" in text
    assert "FILE_BODY" in text or "context compacted" in text


def test_headless_denies_high_risk_and_shell_escape(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "note.txt").write_text("keep", encoding="utf-8")
    registry = ToolRegistry()
    for tool in FileSystemTools(str(workspace)).get_tools():
        registry.register_tool(tool)
    from Kerniq.tools.packs.terminal.tools import TerminalTools

    policy = SecurityPolicy(workspace, require_approval_for_high_risk=True)
    registry.register_tool(TerminalTools(workspace, policy))
    provider = MockProvider(
        [
            _msg(
                "",
                [
                    _call("delete_file", {"path": "note.txt"}, "d1"),
                    _call("run_command", {"command": "cat /etc/passwd"}, "s1"),
                ],
            ),
            _msg("blocked"),
        ]
    )
    agent = Agent(provider, registry)
    agent.orchestrator.security_policy = policy
    result = _run(agent.run("danger", workspace=str(workspace)))
    assert (workspace / "note.txt").exists()
    blob = "\n".join(m.content for m in agent.last_context.messages)
    assert "requires manual approval" in blob
    assert "Absolute paths are denied" in blob or "denied" in blob.lower()
    assert "blocked" in result


def test_verification_failure_is_not_success(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    provider = MockProvider(
        [
            _msg("Attempt one: I did not write marker.txt yet."),
            _msg("Attempt two: the marker file is still missing from the workspace."),
            _msg("Attempt three: giving up without creating marker.txt."),
        ]
    )
    agent = Agent(provider, ToolRegistry())
    from Kerniq.core.verifier import BasicVerifier

    agent.orchestrator.verifier = BasicVerifier()
    result = _run(
        agent.run(
            "create marker",
            workspace=str(workspace),
            checks={"files": ["marker.txt"]},
        )
    )
    assert agent.last_context.metadata["outcome"] == "verification_failed"
    assert "outcome=verification_failed" in result
    assert not (workspace / "marker.txt").exists()


def test_verification_passes_when_file_exists(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("def ready():\n    return 1\n", encoding="utf-8")
    provider = MockProvider([_msg("created")])
    agent = Agent(provider, ToolRegistry())
    from Kerniq.core.verifier import BasicVerifier

    agent.orchestrator.verifier = BasicVerifier()
    result = _run(
        agent.run(
            "create marker",
            workspace=str(workspace),
            checks={"files": ["marker.txt"], "syntax": ["marker.txt"], "contains": {"marker.txt": "def ready"}},
        )
    )
    assert agent.last_context.metadata["outcome"] == "verified"
    assert "outcome=" not in result or "verified" not in result.split("outcome=")[-1][:20] or "unverified" not in result


def test_cancel_finish_reason():
    provider = MockProvider(
        [
            ModelResponse(
                messages=[Message(role=MessageRole.ASSISTANT, content="")],
                finish_reason="cancelled",
                metadata={"cancelled": True},
            )
        ]
    )
    agent = Agent(provider, ToolRegistry())
    result = _run(agent.run("long task"))
    assert agent.last_context.metadata["outcome"] == "cancelled"
    assert "Stopped by user" in result


def test_router_does_not_swap_provider():
    from Kerniq.models.router import ModelRouter

    mock = MockProvider()
    router = ModelRouter([mock])
    assert router.select_provider(preferred_provider_id="mock") is mock
    with pytest.raises(RuntimeError):
        router.select_provider(preferred_provider_id="lm_studio")
    with pytest.raises(RuntimeError):
        router.select_provider(required_capabilities=["vision"])


def test_session_roundtrip_and_corrupt(tmp_path):
    from Kerniq.sessions.manager import SessionManager
    from Kerniq.storage.json_store import JsonStorage

    async def go():
        storage = JsonStorage(tmp_path)
        sm = SessionManager(storage)
        await sm.save_task(
            session_id="abc",
            task_id="t1",
            goal="fix bug",
            status="unverified",
            result="done-ish",
            workspace=str(tmp_path),
            messages=[Message(role=MessageRole.USER, content="fix bug")],
        )
        listed = await sm.list_sessions()
        loaded = await sm.get_session("abc")
        (tmp_path / "session-bad.json").write_text("{not json", encoding="utf-8")
        missing = await sm.get_session("bad")
        listed2 = await sm.list_sessions()
        return listed, loaded, missing, listed2

    listed, loaded, missing, listed2 = _run(go())
    assert listed[0]["goal"] == "fix bug"
    assert loaded["result"] == "done-ish"
    assert loaded["messages"][0]["content"] == "fix bug"
    assert missing is None
    assert all(row["session_id"] != "bad" for row in listed2)


def test_content_loop_stops_after_one_alternative(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    repeated = (
        "The requested file was not created because the workspace policy blocked the write "
        "and the same explanation is being repeated."
    )
    provider = MockProvider([_msg(repeated), _msg(repeated), _msg(repeated)])
    agent = Agent(provider, ToolRegistry())
    from Kerniq.core.verifier import BasicVerifier

    agent.orchestrator.verifier = BasicVerifier()
    result = _run(
        agent.run("create marker", workspace=str(workspace), checks={"files": ["missing.txt"]})
    )
    assert agent.last_context.metadata["outcome"] == "content_loop"
    assert "repeating" in result.lower()


def test_direct_orchestrator_request_shape():
    seen = {}

    class Capture(MockProvider):
        async def generate(self, request: ModelRequest):
            seen["tools"] = request.tools
            seen["n"] = len(request.messages)
            return _msg("ok")

    registry = ToolRegistry()
    orch = Orchestrator(Capture(), registry)
    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="g")
    ctx.add_message(Message(role=MessageRole.USER, content="g"))
    result = _run(orch.run(ctx))
    assert "ok" in result
    assert seen["n"] >= 1
    assert seen["tools"] == []
    _ = GenerationOptions
