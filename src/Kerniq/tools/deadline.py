"""One deadline for every tool. A missing or huge timeout cannot wait forever."""

from __future__ import annotations

from typing import Any

DEFAULT_TOOL_TIMEOUT = 120.0
MAX_TOOL_TIMEOUT = 3600.0


def tool_timeout_seconds(arguments: Any = None, *, fallback: float | None = None, ceiling: float | None = None) -> float:
    """Seconds a tool may run. The argument wins, then the tool default, then 120.

    Anything below 1 becomes 1. Anything above the ceiling (an hour) is cut
    there, so a model cannot pass a timeout that never ends.
    """
    cap = MAX_TOOL_TIMEOUT if ceiling is None else float(ceiling)
    if cap < 1:
        cap = 1.0
    base = DEFAULT_TOOL_TIMEOUT if fallback is None else fallback
    try:
        base = float(base)
    except (TypeError, ValueError):
        base = DEFAULT_TOOL_TIMEOUT
    if base != base or base < 1:  # NaN or non-positive
        base = DEFAULT_TOOL_TIMEOUT
    raw = None
    if isinstance(arguments, dict):
        raw = arguments.get("timeout")
    if raw in (None, ""):
        seconds = base
    else:
        try:
            seconds = float(raw)
        except (TypeError, ValueError):
            seconds = base
    if seconds != seconds or seconds < 1:
        seconds = 1.0
    if seconds > cap:
        seconds = cap
    return seconds
