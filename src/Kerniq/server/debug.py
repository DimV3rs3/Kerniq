"""Admin debug unlock. The token never goes to the model or to other users.

``kerniq server debug on`` prints a token. Opening the UI once with
``?debug=TOKEN`` sets an HttpOnly cookie for that browser only. Host freedom
stays off. The real directory is shown only in that browser.
"""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path
from typing import Any


_COOKIE = "kerniq_debug"


def arm(state_dir: Path | str, enabled: bool) -> dict[str, Any]:
    from .settings import load_server_settings, save_server_settings

    if not enabled:
        save_server_settings(state_dir, {"debug_enabled": False, "debug_token": ""})
        return {"enabled": False, "token": ""}
    token = secrets.token_urlsafe(24)
    save_server_settings(state_dir, {"debug_enabled": True, "debug_token": token})
    current = load_server_settings(state_dir)
    return {"enabled": True, "token": token, "port": int(current.get("port") or 8765)}


def status(state_dir: Path | str) -> dict[str, Any]:
    from .settings import load_server_settings

    current = load_server_settings(state_dir)
    return {"enabled": bool(current.get("debug_enabled"))}


def token_matches(state_dir: Path | str, presented: str) -> bool:
    from .settings import load_server_settings

    current = load_server_settings(state_dir)
    if not current.get("debug_enabled"):
        return False
    expected = str(current.get("debug_token") or "")
    given = str(presented or "")
    if not expected or not given:
        return False
    return hmac.compare_digest(expected, given)


def cookie_value(headers: Any) -> str:
    raw = ""
    if headers is not None:
        raw = str(headers.get("Cookie") or headers.get("cookie") or "")
    for part in raw.split(";"):
        piece = part.strip()
        if piece.startswith(_COOKIE + "="):
            return piece.split("=", 1)[1].strip()
    return ""


def request_unlocked(headers: Any, state_dir: Path | str) -> bool:
    return token_matches(state_dir, cookie_value(headers))


def set_cookie_header(token: str) -> str:
    return f"{_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200"
