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
