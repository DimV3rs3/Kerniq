"""Per-user run queue, the per-minute cap, and parallel tool results."""

import asyncio
import time

from Kerniq.core.orchestrator import Orchestrator
from Kerniq.server.queue import RateWindow, same_user_waiting
from Kerniq.tools.packs.terminal.tools import kill_tree_command


def test_another_user_does_not_block_this_one():
    runs = {
        "a": {"user_id": "alice", "done": False, "queued": False},
    }
    assert same_user_waiting(runs, [], "alice")
    assert not same_user_waiting(runs, [], "bob")
    pending = [("b", "task", {"user_id": "bob"})]
    assert same_user_waiting(runs, pending, "bob")
    assert not same_user_waiting({"a": {"user_id": "alice", "done": True}}, [], "alice")


def test_rate_window_is_per_key():
    window = RateWindow()
    assert window.allow("alice", 2, 0)
    assert window.allow("alice", 2, 1)
    assert not window.allow("alice", 2, 2)
    assert window.allow("bob", 2, 2)
    assert window.allow("alice", 2, 61)
    assert window.allow("alice", 0, 61)


def test_windows_timeout_kills_the_tree(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    assert kill_tree_command(42) == ["taskkill", "/PID", "42", "/T", "/F"]
    monkeypatch.setattr(sys, "platform", "linux")
    assert kill_tree_command(42) is None


def test_parallel_tools_keep_result_order():
    class Call:
        def __init__(self, name, number):
            self.id = "c" + str(number)
            self.name = name
            self.arguments = {"n": number}

    class Tool:
        name = "echo"

        async def execute(self, arguments, context):
            await asyncio.sleep(0.35 if arguments["n"] == 1 else 0.05)

            class Result:
                human_readable = str(arguments["n"])
                output = ""
                stop_reason = ""

            return Result()

    class Context:
        def __init__(self):
            self.messages = []
            self.metadata = {}
            self.cancelled = False

        def add_message(self, message):
            self.messages.append(message)

    orch = Orchestrator(None, None)
    orch.parallel_tools = True
    context = Context()
    tool = Tool()
    started = time.monotonic()
    stopped = asyncio.run(
        orch._execute_parallel([(Call("echo", 1), tool), (Call("echo", 2), tool)], context)
    )
    elapsed = time.monotonic() - started
    assert stopped == ""
    assert elapsed < 0.7
    assert [message.content for message in context.messages] == ["1", "2"]
