"""Every tool has a finite deadline."""

import asyncio

from Kerniq.core.orchestrator import Orchestrator
from Kerniq.tools.deadline import tool_timeout_seconds


def test_timeout_is_capped_and_has_a_default():
    assert tool_timeout_seconds({}) == 120
    assert tool_timeout_seconds({"timeout": 30}) == 30
    assert tool_timeout_seconds({"timeout": "45"}) == 45
    assert tool_timeout_seconds({"timeout": 99999}) == 3600
    assert tool_timeout_seconds({"timeout": 0}, fallback=15) == 1
    assert tool_timeout_seconds({"timeout": "soon"}, fallback=15) == 15
    assert tool_timeout_seconds(None, fallback=9) == 9


def test_a_declared_ceiling_can_exceed_one_hour():
    assert tool_timeout_seconds(None, fallback=5400, ceiling=5400) == 5400
    assert tool_timeout_seconds({"timeout": 120}, fallback=5400, ceiling=5400) == 120
    assert tool_timeout_seconds(None, fallback=999999, ceiling=21600) == 21600


def test_a_settings_deadline_ignores_the_model_timeout(monkeypatch):
    seen = {}

    def spy(arguments=None, *, fallback=None, ceiling=None):
        seen["arguments"] = arguments
        seen["fallback"] = fallback
        seen["ceiling"] = ceiling
        return 30

    monkeypatch.setattr("Kerniq.tools.deadline.tool_timeout_seconds", spy)

    class Tool:
        name = "run_agents"
        tool_id = "run_agents"
        cfg_timeout_from_settings = True
        cfg_default_timeout = 5400
        cfg_timeout_ceiling = 5400

        async def execute(self, arguments, context):
            return "ok"

    class Call:
        id = "c1"
        name = "run_agents"
        arguments = {"timeout": 120}

    class Ctx:
        cancelled = False

    asyncio.run(Orchestrator(None, None)._run_tool_body(Call(), Tool(), Ctx()))
    assert seen["arguments"] is None
    assert seen["fallback"] == 5400
    assert seen["ceiling"] == 5400


def test_a_tool_that_hangs_is_a_timeout(monkeypatch):
    monkeypatch.setattr(
        "Kerniq.tools.deadline.tool_timeout_seconds",
        lambda *args, **kwargs: 0.2,
    )

    class Hang:
        name = "hang"
        tool_id = "hang"

        async def execute(self, arguments, context):
            await asyncio.sleep(30)

    class Call:
        id = "c1"
        name = "hang"
        arguments = {}

    class Ctx:
        cancelled = False

    result = asyncio.run(Orchestrator(None, None)._run_tool_body(Call(), Hang(), Ctx()))
    assert result.stop_reason == "timeout"
    assert result.success is False
    assert "timed out" in result.human_readable.lower()
