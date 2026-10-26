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
