"""A browser cookie is only a user id. No cookie means a new user.

The API key is a second entry point. It is not a substitute for the server
address: a remote console must already know where Kerniq is listening.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Mapping
from uuid import uuid4

COOKIE_NAME = "kerniq_user"
_ID = re.compile(r"^[a-f0-9]{32}$")


def new_user_id() -> str:
    return uuid4().hex


def cookie_header(user_id: str) -> str:
    return f"{COOKIE_NAME}={user_id}; Path=/; HttpOnly; SameSite=Lax"


def _cookie_value(header: str) -> str:
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value.strip()
    return ""


def _presented_key(headers: Mapping[str, str]) -> str:
    auth = str(headers.get("Authorization") or headers.get("authorization") or "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return str(headers.get("X-Kerniq-Key") or headers.get("x-kerniq-key") or "").strip()


def api_user_id(api_key: str) -> str:
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
    return "api:" + digest


def resolve_user(
    headers: Mapping[str, str] | None,
    *,
    server_mode: bool,
    api_key: str = "",
) -> tuple[str, bool, str]:
    """Return ``(user_id, set_cookie, kind)``.

    ``kind`` is ``local``, ``cookie``, ``api``, or ``denied``.
    Local mode is one shared user so a desktop session stays as it was.
    """
    if not server_mode:
        return "local", False, "local"
    headers = headers or {}
    presented = _presented_key(headers)
    if presented:
        if not api_key or not hmac.compare_digest(presented, api_key):
            return "", False, "denied"
        return api_user_id(api_key), False, "api"
    current = _cookie_value(str(headers.get("Cookie") or headers.get("cookie") or ""))
    if _ID.fullmatch(current):
        return current, False, "cookie"
    return new_user_id(), True, "cookie"
