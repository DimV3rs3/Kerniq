"""Chat folding and extractive compaction."""

import importlib.util
from pathlib import Path

from Kerniq.interfaces.models import Message, MessageRole
from Kerniq.persistence.transcript import fold_transcript


def _compactor():
    path = Path(__file__).resolve().parents[2] / "plugins" / "context_compact" / "main.py"
    spec = importlib.util.spec_from_file_location("context_compact_main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PluginImpl()


def test_thoughts_between_reads_collapse_and_merge():
    messages = [
        {"kind": "think_collapsed", "text": "first"},
        {"kind": "tool", "name": "read_file", "status": "success", "success": True},
        {"kind": "think_collapsed", "text": "second"},
        {"kind": "tool", "name": "read_file", "status": "success", "success": True},
        {"kind": "think_collapsed", "text": "third"},
        {"kind": "tool", "name": "create_file", "status": "success", "success": True},
    ]
    folded = fold_transcript(messages, aggregate=True, collapsible={"read_file"})
    kinds = [(m.get("kind"), m.get("name"), m.get("text"), m.get("count")) for m in folded]
    assert kinds == [
        ("tool_agg", "read_file", None, 2),
        ("think_collapsed", None, "third", None),
        ("tool", "create_file", None, None),
    ]


def test_compact_keeps_omitted_facts():
    plugin = _compactor()
    plugin.cfg_keep_last = 1
    messages = [
        Message(role=MessageRole.SYSTEM, content="system"),
        Message(role=MessageRole.USER, content="fix parser.py"),
        Message(role=MessageRole.ASSISTANT, content="I will edit src/parser.py and keep token MAX_TOKENS"),
        Message(role=MessageRole.USER, content="go on"),
        Message(role=MessageRole.ASSISTANT, content="done"),
    ]
    out = plugin.compact(messages)
    blob = "\n".join(m.content for m in out)
    assert "parser.py" in blob
    assert "MAX_TOKENS" in blob
    assert "fix parser.py" in blob
    assert any(m.content == "done" for m in out)
