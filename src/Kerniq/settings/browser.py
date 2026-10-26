"""Browser-owned settings. Used when server mode must not fill the disk.

The API token is a user setting. In server mode the server does not keep it
and does not return a stored token. The browser sends it only with the run.
"""

from __future__ import annotations

from typing import Any


_SECTIONS = ("chat", "agent", "api", "prompt", "interface")


def public_settings(payload: dict[str, Any], *, server_mode: bool) -> dict[str, Any]:
    """Settings a browser may see. Server mode never includes the API token."""
    out = dict(payload or {})
    if not server_mode:
        return out
    api = dict(out.get("api") or {})
    api["api_token"] = ""
    api.pop("api_token_sealed", None)
    out["api"] = api
    agent = dict(out.get("agent") or {})
    agent["workspace"] = "/workspace"
    out["agent"] = agent
    out["client_owned"] = True
    return out


def overlay_settings(ui: Any, client: Any) -> Any:
    """Return a copy of ``ui`` with this request's browser settings applied.

    The copy is not saved. A missing section leaves the current value.
    """
    data = ui.model_dump()
    if isinstance(client, dict):
        for section in _SECTIONS:
            block = client.get(section)
            current = data.get(section)
            if not isinstance(block, dict) or not isinstance(current, dict):
                continue
            for key, value in block.items():
                if key == "api_token_sealed":
                    continue
                current[key] = value
    return type(ui).model_validate(data)
