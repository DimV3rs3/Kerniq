"""Basic at-rest protection for the API token.

The ciphertext is stored in settings.json. The key stays in
``state/.settings.key``, which uninstall deletes with the rest of state/.
This is not a vault. It only keeps the token from sitting in the JSON as
plaintext.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

_PREFIX = "enc:v1:"
_KEY_NAME = ".settings.key"


def _key_path(state_dir: Path | str) -> Path:
    return Path(state_dir) / _KEY_NAME


def _load_key(state_dir: Path | str) -> bytes:
    path = _key_path(state_dir)
    if path.is_file():
        raw = path.read_bytes()
        if len(raw) >= 32:
            return raw[:32]
    path.parent.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _stream(key: bytes, nonce: bytes, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:size])


def encrypt_secret(state_dir: Path | str, plain: str) -> str:
    text = plain or ""
    if not text or text.startswith(_PREFIX):
        return text
    key = _load_key(state_dir)
    nonce = os.urandom(16)
    raw = text.encode("utf-8")
    stream = _stream(key, nonce, len(raw))
    cipher = bytes(a ^ b for a, b in zip(raw, stream))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    blob = base64.urlsafe_b64encode(nonce + mac + cipher).decode("ascii")
    return _PREFIX + blob


def decrypt_secret(state_dir: Path | str, stored: str) -> str:
    text = stored or ""
    if not text.startswith(_PREFIX):
        return text
    path = _key_path(state_dir)
    if not path.is_file():
        return ""
    key = path.read_bytes()[:32]
    try:
        packed = base64.urlsafe_b64decode(text[len(_PREFIX):].encode("ascii"))
    except Exception:
        return ""
    if len(packed) < 16 + 32:
        return ""
    nonce, mac, cipher = packed[:16], packed[16:48], packed[48:]
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        return ""
    stream = _stream(key, nonce, len(cipher))
    try:
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")
    except Exception:
        return ""


def seal_settings(state_dir: Path | str, data: dict[str, Any]) -> dict[str, Any]:
    api = data.get("api")
    if not isinstance(api, dict):
        return data
    token = api.get("api_token")
    if not isinstance(token, str) or not token or token.startswith(_PREFIX):
        return data
    sealed = dict(data)
    sealed_api = dict(api)
    sealed_api["api_token"] = encrypt_secret(state_dir, token)
    sealed["api"] = sealed_api
    return sealed


def open_settings(state_dir: Path | str, data: dict[str, Any]) -> dict[str, Any]:
    api = data.get("api")
    if not isinstance(api, dict):
        return data
    token = api.get("api_token")
    if not isinstance(token, str) or not token.startswith(_PREFIX):
        return data
    opened = dict(data)
    opened_api = dict(api)
    opened_api["api_token"] = decrypt_secret(state_dir, token)
    opened["api"] = opened_api
    return opened


def token_is_plaintext(data: dict[str, Any]) -> bool:
    api = data.get("api") if isinstance(data, dict) else None
    token = api.get("api_token") if isinstance(api, dict) else ""
    return isinstance(token, str) and bool(token) and not token.startswith(_PREFIX)


_SIG_NAME = "settings.json.sig"
_SAFE_CRITICAL = {
    "host_freedom": False,
    "allow_elevated": False,
    "use_venv": True,
    "workspace": "./workspace",
    "attachments": "./attachments",
    "downloads": "./downloads",
    "auto_approve_up_to": "low",
    "developer_mode": False,
}


def critical_settings(data: dict[str, Any]) -> dict[str, Any]:
    """The fields that turn the sandbox off. These are what the signature covers."""
    agent = data.get("agent") if isinstance(data.get("agent"), dict) else {}
    chat = data.get("chat") if isinstance(data.get("chat"), dict) else {}
    if "use_venv" in agent:
        use_venv = bool(agent.get("use_venv"))
    else:
        use_venv = True
    return {
        "host_freedom": bool(agent.get("host_freedom")),
        "allow_elevated": bool(agent.get("allow_elevated")),
        "use_venv": use_venv,
        "workspace": str(agent.get("workspace") or "./workspace"),
        "attachments": str(agent.get("attachments") or "./attachments"),
        "downloads": str(agent.get("downloads") or "./downloads"),
        "auto_approve_up_to": str(chat.get("auto_approve_up_to") or "low"),
        "developer_mode": bool(chat.get("developer_mode")),
    }


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _signature_status(state_dir: Path | str, payload: dict[str, Any]) -> str:
    path = Path(state_dir) / _SIG_NAME
    if not path.is_file():
        return "missing"
    key_path = _key_path(state_dir)
    if not key_path.is_file():
        return "bad"
    key = key_path.read_bytes()[:32]
    if len(key) < 32:
        return "bad"
    expected = hmac.new(key, _canonical(payload), hashlib.sha256).hexdigest()
    try:
        got = path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeError):
        return "bad"
    if len(got) != len(expected) or not hmac.compare_digest(expected, got):
        return "bad"
    return "ok"


def sign_critical(state_dir: Path | str, data: dict[str, Any]) -> None:
    """Sign the privileged fields with state/.settings.key."""
    key = _load_key(state_dir)
    mac = hmac.new(key, _canonical(critical_settings(data)), hashlib.sha256).hexdigest()
    path = Path(state_dir) / _SIG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mac + "\n", encoding="ascii")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _apply_critical(data: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(data)
    agent = out.get("agent")
    if not isinstance(agent, dict):
        agent = {}
        out["agent"] = agent
    chat = out.get("chat")
    if not isinstance(chat, dict):
        chat = {}
        out["chat"] = chat
    agent["host_freedom"] = bool(payload["host_freedom"])
    agent["allow_elevated"] = bool(payload["allow_elevated"])
    agent["use_venv"] = bool(payload["use_venv"])
    agent["workspace"] = payload["workspace"]
    agent["attachments"] = payload["attachments"]
    agent["downloads"] = payload["downloads"]
    chat["auto_approve_up_to"] = payload["auto_approve_up_to"]
    chat["developer_mode"] = bool(payload["developer_mode"])
    return out


def vet_settings(state_dir: Path | str, data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Check the signature. Return ``(data, rewrite)``.

    No signature yet (an upgrade): keep the workspace, but drop an unsigned
    ``host_freedom``, elevated mode, or a venv that was switched off. Those
    cannot arrive from a file the sandbox was able to plant.

    A signature that does not match: the file was edited outside Kerniq.
    Privileged fields return to the safe defaults, including the workspace.
    The caller rewrites the file and signs that result. A missing signature
    on an otherwise safe file is signed in place.
    """
    if not isinstance(data, dict) or not data:
        return (data if isinstance(data, dict) else {}), False
    current = critical_settings(data)
    status = _signature_status(state_dir, current)
    if status == "ok":
        return data, False
    if status == "missing":
        adopted = dict(current)
        adopted["host_freedom"] = False
        adopted["allow_elevated"] = False
        if not current["use_venv"]:
            adopted["use_venv"] = True
        ceiling = str(current["auto_approve_up_to"] or "").strip().lower()
        if ceiling in {"all", "bypass"}:
            adopted["auto_approve_up_to"] = "low"
        if adopted == current:
            sign_critical(state_dir, data)
            return data, False
        return _apply_critical(data, adopted), True
    return _apply_critical(data, dict(_SAFE_CRITICAL)), True

