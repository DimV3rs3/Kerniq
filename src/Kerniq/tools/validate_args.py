"""Minimal JSON Schema checks for tool arguments.

Rejects missing required fields and obvious type mismatches before a tool
runs. Unknown extra keys are allowed so older models are not blocked by
optional metadata such as tool_call_id.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def argument_error(schema: Optional[Dict[str, Any]], arguments: Any) -> Optional[str]:
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return "arguments must be a JSON object"
    if not schema:
        return None
    if schema.get("type") not in (None, "object"):
        return None
    required = schema.get("required") or []
    props = schema.get("properties") or {}
    for key in required:
        if key not in arguments or arguments[key] is None or arguments[key] == "":
            return f"missing required argument: {key}"
    for key, value in arguments.items():
        if key in ("tool_call_id",):
            continue
        spec = props.get(key)
        if not isinstance(spec, dict):
            continue
        expected = spec.get("type")
        if expected == "integer" and isinstance(value, bool):
            return f"argument {key} must be an integer"
        py_type = _TYPE_MAP.get(expected)
        if py_type is not None and not isinstance(value, py_type):
            return f"argument {key} must be a {expected}"
    return None
