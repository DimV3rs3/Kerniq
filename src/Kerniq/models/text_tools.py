"""Tool calls written as text.

Some models print a call instead of using the native tool channel, even when
they were trained for native tools. One recovered call must not turn native
tools off: the orchestrator still sends schemas, and this parser is only a
fallback for the turn that missed the channel.

Accepted shapes, with optional space or newline between the name and the JSON:

* ``update_plan{"items": [...]}``
* ``update_plan[{...}, {...}]`` — a bare array is the ``items`` argument
* ``name{bare_key: value}`` and the ``<|"|>`` quote marker
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

from Kerniq.interfaces.models import ToolCall

TEXT_PROTOCOL = (
    "This model cannot call tools natively. To use a tool, write it as text on its own, "
    "with a JSON object of arguments and double quotes: tool_name{\"arg\": \"value\"}. "
    "A bare JSON array after the name is the items argument. "
    "Do not wrap the call in a sentence. You may write several calls."
)

_QUOTE_MARKERS = (
    '<|"|>',
    "<|'|>",
    "“",
    "”",
    "«",
    "»",
)
_CALL = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][\w]*)\s*([{\[])")
_BARE_KEY = re.compile(r"([{\[,]\s*)([A-Za-z_][\w]*)\s*:")
# Names whose only argument is a list. A bare array is that argument.
_LIST_ARGUMENT = {"update_plan": "items"}


def normalize_tool_text(text: str) -> str:
    out = text or ""
    for marker in _QUOTE_MARKERS:
        out = out.replace(marker, '"')
    return out


def _loads(blob: str) -> Optional[Any]:
    value = _parse_json(blob)
    if value is None and blob[:1] == "{":
        value = _parse_json(_BARE_KEY.sub(r'\1"\2":', blob))
    if isinstance(value, (dict, list)):
        return value
    return None


def _parse_json(blob: str) -> Optional[Any]:
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _as_arguments(name: str, value: Any) -> Optional[dict]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        key = _LIST_ARGUMENT.get(name, "items")
        return {key: value}
    return None


def _balanced(text: str, start: int) -> Tuple[str, int]:
    opener = text[start] if start < len(text) else ""
    closer = "}" if opener == "{" else "]" if opener == "[" else ""
    if not closer:
        return "", start
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
            if depth == 0 and char == closer:
                return text[start:index + 1], index + 1
            if depth < 0:
                return "", start
    return "", start


def parse_text_tool_calls(text: str, names: Iterable[str], schemas: Optional[dict] = None) -> Tuple[str, List[ToolCall]]:
    """Pull known tool calls out of assistant text. Unknown braces stay put.

    ``schemas`` maps a tool name to its argument names, in order. A call written
    as ``name(...)`` uses that order for positional values. Named ``key: value``
    and ``key=value`` win over a positional duplicate.
    """
    allowed = {str(name) for name in names if name}
    if not text or not allowed:
        return text or "", []
    found = _find_invocations(text, allowed, schemas or {})
    if not found:
        return _parse_braced(text, allowed)
    pieces: List[str] = []
    calls: List[ToolCall] = []
    cursor = 0
    for start, end, call in found:
        gap_text, gap_calls = _parse_braced(text[cursor:start], allowed)
        pieces.append(gap_text if gap_calls else text[cursor:start])
        calls.extend(gap_calls)
        calls.append(call)
        cursor = end
    tail_text, tail_calls = _parse_braced(text[cursor:], allowed)
    pieces.append(tail_text if tail_calls else text[cursor:])
    return "".join(pieces).strip(), calls


def _parse_braced(text: str, allowed: set) -> Tuple[str, List[ToolCall]]:
    normalized = normalize_tool_text(text)
    calls: List[ToolCall] = []
    pieces: List[str] = []
    cursor = 0
    for match in _CALL.finditer(normalized):
        name = match.group(1)
        if name not in allowed or match.start() < cursor:
            continue
        blob, end = _balanced(normalized, match.end() - 1)
        if not blob:
            continue
        arguments = _as_arguments(name, _loads(blob))
        if arguments is None:
            continue
        pieces.append(normalized[cursor:match.start()])
        cursor = end
        calls.append(ToolCall(id=str(uuid4()), name=name, arguments=arguments))
    if not calls:
        return text, []
    pieces.append(normalized[cursor:])
    return "".join(pieces).strip(), calls


_INVOKE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][\w]*)\s*\(")
_MISSING = object()
_MARK_QUOTES = ('<|"|>', "<|'|>")
_FALLBACK_SLOTS = ("path", "content", "old_string", "new_string", "text", "query", "command", "pattern")


def _find_invocations(text: str, allowed: set, schemas: dict):
    found = []
    cursor = 0
    while cursor < len(text):
        match = _INVOKE.search(text, cursor)
        if match is None:
            break
        name = match.group(1)
        if name not in allowed:
            cursor = match.end()
            continue
        parsed = _read_invocation(text, match.end(), name, schemas)
        if parsed is None:
            cursor = match.end()
            continue
        arguments, end = parsed
        found.append((match.start(), end, ToolCall(id=str(uuid4()), name=name, arguments=arguments)))
        cursor = max(end, match.end())
    return found


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _skip_sep(text: str, index: int) -> int:
    while index < len(text):
        index = _skip_ws(text, index)
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        break
    return index


def _peek_key(text: str, index: int) -> Optional[str]:
    matched = re.match(r"[A-Za-z_][\w]*", text[index:])
    if matched is None:
        return None
    after = _skip_ws(text, index + matched.end())
    if after < len(text) and text[after] in ":=":
        return matched.group(0)
    return None


def _read_quoted(text: str, index: int):
    escaped = False
    for cursor in range(index + 1, len(text)):
        char = text[cursor]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            blob = text[index:cursor + 1]
            try:
                return json.loads(blob), cursor + 1
            except json.JSONDecodeError:
                return blob[1:-1], cursor + 1
    return _MISSING, index


def _read_verbatim(text: str, index: int):
    """C# verbatim string. ``""`` is one quote. One leading newline is the opener."""
    chars: List[str] = []
    while index < len(text):
        if text[index] == '"':
            if index + 1 < len(text) and text[index + 1] == '"':
                chars.append('"')
                index += 2
                continue
            value = "".join(chars)
            if value.startswith("\n"):
                value = value[1:]
            return value, index + 1
        chars.append(text[index])
        index += 1
    return _MISSING, index


def _read_value(text: str, index: int):
    index = _skip_ws(text, index)
    if index >= len(text):
        return _MISSING, index
    if text.startswith('@"', index):
        return _read_verbatim(text, index + 2)
    if text.startswith('"""', index):
        end = text.find('"""', index + 3)
        if end < 0:
            return _MISSING, index
        return text[index + 3:end], end + 3
    for mark in _MARK_QUOTES:
        if text.startswith(mark, index):
            end = text.find(mark, index + len(mark))
            if end < 0:
                return _MISSING, index
            return text[index + len(mark):end], end + len(mark)
    if text[index] == '"':
        return _read_quoted(text, index)
    if text[index] == "'":
        end = text.find("'", index + 1)
        if end < 0:
            return _MISSING, index
        return text[index + 1:end], end + 1
    if text[index] in "{[":
        blob, end = _balanced(text, index)
        loaded = _loads(blob) if blob else None
        if loaded is None:
            return _MISSING, index
        return loaded, end
    word = re.match(r"[A-Za-z_][\w]*", text[index:])
    if word is not None:
        ident = word.group(0)
        low = ident.lower()
        nxt = index + word.end()
        if low == "true":
            return True, nxt
        if low == "false":
            return False, nxt
        if low in ("null", "none"):
            return None, nxt
        if "/" in ident or "." in ident:
            return ident, nxt
        return _MISSING, index
    number = re.match(r"-?\d+(?:\.\d+)?", text[index:])
    if number is not None:
        raw = number.group(0)
        value = float(raw) if "." in raw else int(raw)
        return value, index + len(raw)
    return _MISSING, index


def _bind_args(name: str, named: dict, positional: List[Any], schemas: dict) -> Optional[dict]:
    slots = [str(item) for item in (schemas.get(name) or []) if item]
    if not slots:
        slots = list(_FALLBACK_SLOTS)
    args = {key: value for key, value in named.items() if value is not None}
    for value in positional:
        if isinstance(value, list) and _LIST_ARGUMENT.get(name, "items") not in args:
            args[_LIST_ARGUMENT.get(name, "items")] = value
            continue
        if isinstance(value, str) and any(isinstance(have, str) and have == value for have in args.values()):
            continue
        for key in slots:
            if key not in args:
                args[key] = value
                break
        else:
            if isinstance(value, str) and "content" not in args:
                args["content"] = value
    if not args or not any(value not in ("", None, [], {}) for value in args.values()):
        return None
    return args


def _trailer_end(text: str, index: int) -> int:
    index = _skip_ws(text, index)
    if index < len(text) and text[index] == ")":
        index += 1
        index = _skip_ws(text, index)
    if index < len(text) and text[index] == "}":
        nxt = _skip_ws(text, index + 1)
        if nxt >= len(text) or text.startswith("<tool_call", nxt) or text.startswith("</tool_call", nxt):
            index = nxt
    if text.startswith("<tool_call", index) or text.startswith("</tool_call", index):
        close = text.find(">", index)
        index = len(text) if close < 0 else close + 1
    return index


def _skip_stray_mark(text: str, index: int) -> int:
    """Drop a quote marker glued on after a value, before the next comma.

    Models trained on ``<|"|>`` sometimes close a real string and then emit
    another marker, so ``"value"<|"|>,path:`` is still ``,path:``.
    """
    for mark in _MARK_QUOTES:
        if not text.startswith(mark, index):
            continue
        nxt = index + len(mark)
        end = text.find(mark, nxt)
        if end < 0:
            return index
        body = text[nxt:end]
        if body == "" or body[:1] in ",:":
            return nxt
    return index


def _read_invocation(text: str, start: int, name: str, schemas: dict):
    index = start
    named: dict = {}
    positional: List[Any] = []
    saw = False
    limit = len(text)
    while index < limit:
        index = _skip_sep(text, index)
        index = _skip_stray_mark(text, index)
        index = _skip_sep(text, index)
        if index >= limit:
            break
        if text.startswith("<tool_call", index) or text.startswith("</tool_call", index):
            break
        if text[index] in ")}":
            break
        key = _peek_key(text, index)
        if key is not None:
            cursor = _skip_ws(text, index + len(key))
            cursor += 1  # : or =
            value, cursor = _read_value(text, cursor)
            if value is _MISSING:
                break
            named[key] = value
            saw = True
            index = cursor
            continue
        value, cursor = _read_value(text, index)
        if value is _MISSING or cursor == index:
            break
        positional.append(value)
        saw = True
        index = cursor
    if not saw:
        return None
    arguments = _bind_args(name, named, positional, schemas)
    if arguments is None:
        return None
    return arguments, _trailer_end(text, index)


_CHANNEL_BLOCK = re.compile(
    r"<(?:tool_call|toolcall)>\s*(.*?)\s*</(?:tool_call|toolcall)>",
    re.I | re.S,
)
_CHANNEL_REQUEST = re.compile(
    r"\[TOOL_REQUEST\]\s*(.*?)\s*\[END_TOOL_REQUEST\]",
    re.I | re.S,
)


def _call_from_channel(blob: str) -> Optional[ToolCall]:
    """The call LM Studio's own template asks the model to emit."""
    raw = (blob or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[A-Za-z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    value = _loads(raw) if raw.startswith("{") else None
    if not isinstance(value, dict):
        start = raw.find("{")
        if start >= 0:
            balanced, _end = _balanced(raw, start)
            value = _loads(balanced) if balanced else None
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or value.get("tool") or "").strip()
    if not name or not re.match(r"[A-Za-z_][\w]*$", name):
        return None
    arguments = value.get("arguments", value.get("parameters"))
    if isinstance(arguments, str):
        parsed = _loads(arguments)
        arguments = parsed if isinstance(parsed, (dict, list)) else {"raw": arguments}
    if isinstance(arguments, list):
        arguments = {"items": arguments}
    if not isinstance(arguments, dict):
        arguments = {}
    return ToolCall(id=str(uuid4()), name=name, arguments=arguments)


def extract_channel_tool_calls(text: str) -> Tuple[str, List[ToolCall]]:
    """Lift the call formats LM Studio's own templates ask the model to emit.

    Qwen-style templates use ``<tool_call>{"name", "arguments"}</tool_call>``
    or ``[TOOL_REQUEST]…[END_TOOL_REQUEST]``. Gemma 4 uses
    ``<|tool_call>call:name{key:<|"|>value<|"|>}<tool_call|>``. When the server
    fails to parse a slightly off block it returns the tags as plain content.
    That is still the model's native tool channel, not a second protocol.
    """
    if not text:
        return text or "", []
    calls: List[ToolCall] = []

    def _take(match: re.Match) -> str:
        call = _call_from_channel(match.group(1))
        if call is None:
            return match.group(0)
        calls.append(call)
        return ""

    cleaned = _CHANNEL_BLOCK.sub(_take, text)
    cleaned = _CHANNEL_REQUEST.sub(_take, cleaned)
    gemma_text, gemma_calls = _extract_gemma_calls(cleaned)
    if gemma_calls:
        cleaned = gemma_text
        calls.extend(gemma_calls)
    return cleaned.strip(), calls


_GEMMA_MARK = '<|"|>'
_GEMMA_CALL = re.compile(r"call:([A-Za-z_][\w.\-]*)\s*\{")
_GEMMA_CLOSER = re.compile(r"\s*(?:<tool_call\|>|</tool_call>)", re.I)


def _parse_gemma_value(text: str, index: int) -> Tuple[Any, int]:
    size = len(text)
    while index < size and text[index] in " \t\r\n":
        index += 1
    if index >= size:
        return None, index
    if text.startswith(_GEMMA_MARK, index):
        end = text.find(_GEMMA_MARK, index + len(_GEMMA_MARK))
        if end < 0:
            return text[index + len(_GEMMA_MARK):], size
        return text[index + len(_GEMMA_MARK):end], end + len(_GEMMA_MARK)
    if text[index] == "{":
        value, index, _closed = _parse_gemma_object(text, index + 1)
        return value, index
    if text[index] == "[":
        value, index, _closed = _parse_gemma_array(text, index + 1)
        return value, index
    start = index
    while index < size and text[index] not in ",}]":
        index += 1
    raw = text[start:index].strip()
    low = raw.lower()
    if low == "true":
        return True, index
    if low == "false":
        return False, index
    if low in ("null", "none"):
        return None, index
    if re.fullmatch(r"-?\d+", raw):
        return int(raw), index
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw), index
    return raw, index


def _parse_gemma_object(text: str, index: int) -> Tuple[dict, int, bool]:
    obj: dict = {}
    size = len(text)
    while index < size:
        while index < size and text[index] in " \t\r\n,":
            index += 1
        if index >= size:
            return obj, index, False
        if text[index] == "}":
            return obj, index + 1, True
        matched = re.match(r"[A-Za-z_][\w]*", text[index:])
        if not matched:
            return obj, index, False
        key = matched.group(0)
        index += len(key)
        while index < size and text[index] in " \t\r\n":
            index += 1
        if index >= size or text[index] != ":":
            return obj, index, False
        index += 1
        value, index = _parse_gemma_value(text, index)
        obj[key] = value
    return obj, index, False


def _parse_gemma_array(text: str, index: int) -> Tuple[list, int, bool]:
    items: list = []
    size = len(text)
    while index < size:
        while index < size and text[index] in " \t\r\n,":
            index += 1
        if index >= size:
            return items, index, False
        if text[index] == "]":
            return items, index + 1, True
        value, index = _parse_gemma_value(text, index)
        items.append(value)
    return items, index, False


def _extract_gemma_calls(text: str) -> Tuple[str, List[ToolCall]]:
    """Gemma 4 function calls. Strings stay literal between ``<|"|>`` markers."""
    if not text or "call:" not in text:
        return text, []
    calls: List[ToolCall] = []
    pieces: List[str] = []
    cursor = 0
    while True:
        start = text.find("call:", cursor)
        if start < 0:
            pieces.append(text[cursor:])
            break
        matched = _GEMMA_CALL.match(text, start)
        if not matched:
            pieces.append(text[cursor:start + 5])
            cursor = start + 5
            continue
        window = text[max(0, start - 48):start].lower()
        opened = "tool_call" in window or "toolcall" in window
        arguments, end, closed = _parse_gemma_object(text, matched.end())
        closer = _GEMMA_CLOSER.match(text, end) if closed else None
        if not closed or (not opened and closer is None):
            pieces.append(text[cursor:start + 5])
            cursor = start + 5
            continue
        piece = text[cursor:start]
        if opened:
            piece = re.sub(r"<(?:\|)?tool_call(?:>|\|)?\s*$", "", piece, flags=re.I)
        pieces.append(piece)
        calls.append(ToolCall(
            id=str(uuid4()),
            name=matched.group(1),
            arguments=arguments if isinstance(arguments, dict) else {},
        ))
        cursor = closer.end() if closer else end
    return "".join(pieces).strip(), calls


def adopt_channel_calls(content: str, tool_calls: Optional[List[ToolCall]]) -> Tuple[str, Optional[List[ToolCall]]]:
    cleaned, found = extract_channel_tool_calls(content or "")
    if not found:
        return content or "", tool_calls
    if tool_calls:
        return cleaned, tool_calls
    return cleaned, found


def normalize_parameters(params: Any) -> dict:
    """JSON Schema object, the shape LM Studio copies into the chat template."""
    if not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    out = dict(params)
    if out.get("type") != "object":
        out["type"] = "object"
    if not isinstance(out.get("properties"), dict):
        out["properties"] = {}
    return out


def protocol_messages(messages: Sequence, protocol: str = TEXT_PROTOCOL):
    """Return a copy of messages with the text-tool note on the system prompt."""
    from Kerniq.interfaces.models import Message, MessageRole

    copied = []
    injected = False
    for message in messages:
        if not injected and message.role == MessageRole.SYSTEM:
            copied.append(Message(
                role=MessageRole.SYSTEM,
                content=((message.content or "").rstrip() + "\n\n" + protocol).strip(),
                tool_calls=message.tool_calls,
                tool_call_id=message.tool_call_id,
                name=message.name,
                metadata=message.metadata,
            ))
            injected = True
        else:
            copied.append(message)
    if not injected:
        copied.insert(0, Message(role=MessageRole.SYSTEM, content=protocol))
    return copied
