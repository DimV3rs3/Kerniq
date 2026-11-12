"""Plugins that are loaded in this process.

Kerniq does not know any plugin by name. After a plugin starts, it can add a
system-prompt note and it can narrow the tool list the model sees. Workers and
other callers that read the tool registry directly are not filtered here.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_plugins: dict[str, object] = {}


def note_live(plugin_id: str, plugin: object) -> None:
    if not plugin_id or plugin is None:
        return
    with _lock:
        _plugins[str(plugin_id)] = plugin


def drop_live(plugin_id: str) -> None:
    if not plugin_id:
        return
    with _lock:
        _plugins.pop(str(plugin_id), None)


def _snapshot() -> list[object]:
    with _lock:
        return list(_plugins.values())


def model_system_notes(mode: str) -> str:
    """Text from loaded plugins, appended after Kerniq's own prompt."""
    parts: list[str] = []
    for plugin in _snapshot():
        fn = getattr(plugin, "system_note", None)
        if not callable(fn):
            continue
        try:
            text = fn(mode)
        except Exception:
            continue
        text = str(text or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def apply_model_tool_filters(specs, mode: str, tools: dict | None = None):
    """Each loaded plugin may return a shorter spec list. A failure leaves the list as it was."""
    current = list(specs or [])
    for plugin in _snapshot():
        fn = getattr(plugin, "filter_model_tools", None)
        if not callable(fn):
            continue
        try:
            nxt = fn(current, mode, tools)
        except TypeError:
            try:
                nxt = fn(current, mode)
            except Exception:
                continue
        except Exception:
            continue
        if isinstance(nxt, list):
            current = nxt
    return current
