"""Core server settings. The web plugin can edit the same values; it does not own them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

JSON_STORAGE_WARNING = (
    "No database is connected. Chats and replies are stored in JSON."
)
_FILE = "server.json"


def _path(state_dir: Path | str) -> Path:
    from ..devtools.paths import anchored_dir

    return anchored_dir(state_dir) / _FILE


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _secret(state_dir: Path, stored: str) -> str:
    if not stored:
        return ""
    from ..settings.secrets import decrypt_secret

    try:
        return decrypt_secret(state_dir, stored)
    except Exception:
        return stored if not str(stored).startswith("enc:v1:") else ""


def _seal(state_dir: Path, plain: str) -> str:
    if not plain:
        return ""
    from ..settings.secrets import encrypt_secret

    return encrypt_secret(state_dir, plain)


def load_server_settings(state_dir: Path | str, config: Any = None) -> dict[str, Any]:
    """Platform config, then state/server.json, then environment.

    Empty environment variables do not wipe a saved value.
    """
    import os

    from ..devtools.paths import anchored_dir

    root = anchored_dir(state_dir)
    out: dict[str, Any] = {
        "enabled": False,
        "host": "127.0.0.1",
        "port": 8765,
        "database_url": "",
        "api_key": "",
        "lan_access": False,
        "users_root": "",
        "users_roots": [],
        "user_quota_bytes": 8 * 1024 * 1024 * 1024,
        "model_base_url": "http://127.0.0.1:1234",
        "debug_enabled": False,
        "debug_token": "",
    }
    server = getattr(config, "server", None) if config is not None else None
    if server is not None:
        out["enabled"] = bool(getattr(server, "enabled", False))
        out["host"] = str(getattr(server, "host", out["host"]) or out["host"])
        try:
            out["port"] = int(getattr(server, "port", out["port"]) or out["port"])
        except (TypeError, ValueError):
            out["port"] = 8765
        out["database_url"] = str(getattr(server, "database_url", "") or "")
    ui = getattr(config, "ui", None) if config is not None else None
    if ui is not None and not out["enabled"]:
        # [ui] host is the historical bind. It still counts when server.json
        # has not stored a public address of its own.
        ui_host = str(getattr(ui, "host", "") or "")
        if ui_host and out["host"] in {"", "127.0.0.1", "localhost"}:
            out["host"] = ui_host
    raw = _read(_path(root))
    if "enabled" in raw:
        out["enabled"] = bool(raw.get("enabled"))
    if raw.get("host"):
        out["host"] = str(raw.get("host"))
    if raw.get("port"):
        try:
            out["port"] = int(raw.get("port"))
        except (TypeError, ValueError):
            pass
    if "lan_access" in raw:
        out["lan_access"] = bool(raw.get("lan_access"))
    if raw.get("database_url"):
        out["database_url"] = _secret(root, str(raw.get("database_url")))
    if raw.get("api_key"):
        out["api_key"] = _secret(root, str(raw.get("api_key")))
    if raw.get("users_root"):
        out["users_root"] = str(raw.get("users_root"))
    extras = raw.get("users_roots")
    if isinstance(extras, list):
        out["users_roots"] = [str(item) for item in extras if str(item or "").strip()]
    if raw.get("model_base_url"):
        out["model_base_url"] = str(raw.get("model_base_url"))
    if "debug_enabled" in raw:
        out["debug_enabled"] = bool(raw.get("debug_enabled"))
    if raw.get("debug_token"):
        out["debug_token"] = _secret(root, str(raw.get("debug_token")))
    if raw.get("user_quota_bytes"):
        try:
            out["user_quota_bytes"] = int(raw.get("user_quota_bytes"))
        except (TypeError, ValueError):
            pass
    if os.environ.get("KERNIQ_SERVER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        out["enabled"] = True
    if os.environ.get("KERNIQ_DATABASE_URL", "").strip():
        out["database_url"] = os.environ["KERNIQ_DATABASE_URL"].strip()
    if os.environ.get("KERNIQ_API_KEY", "").strip():
        out["api_key"] = os.environ["KERNIQ_API_KEY"].strip()
    if os.environ.get("KERNIQ_USERS_ROOT", "").strip():
        out["users_root"] = os.environ["KERNIQ_USERS_ROOT"].strip()
    if os.environ.get("KERNIQ_MODEL_URL", "").strip():
        out["model_base_url"] = os.environ["KERNIQ_MODEL_URL"].strip()
    if os.environ.get("KERNIQ_USER_QUOTA_GB", "").strip():
        try:
            out["user_quota_bytes"] = int(float(os.environ["KERNIQ_USER_QUOTA_GB"]) * 1024 * 1024 * 1024)
        except ValueError:
            pass
    return out


def save_server_settings(state_dir: Path | str, values: dict[str, Any]) -> dict[str, Any]:
    """Merge and store. Secrets are sealed. The returned dict is plaintext."""
    from ..devtools.paths import anchored_dir

    root = anchored_dir(state_dir)
    current = load_server_settings(root)
    for key in (
        "enabled", "host", "port", "database_url", "api_key", "lan_access",
        "users_root", "users_roots", "user_quota_bytes", "model_base_url",
        "debug_enabled", "debug_token",
    ):
        if key in values and values[key] is not None:
            current[key] = values[key]
    try:
        current["port"] = int(current.get("port") or 8765)
    except (TypeError, ValueError):
        current["port"] = 8765
    try:
        current["user_quota_bytes"] = int(current.get("user_quota_bytes") or 0)
    except (TypeError, ValueError):
        current["user_quota_bytes"] = 8 * 1024 * 1024 * 1024
    current["enabled"] = bool(current.get("enabled"))
    current["lan_access"] = bool(current.get("lan_access"))
    current["host"] = str(current.get("host") or "127.0.0.1")
    current["users_root"] = str(current.get("users_root") or "")
    roots = current.get("users_roots")
    if not isinstance(roots, list):
        roots = []
    current["users_roots"] = [str(item) for item in roots if str(item or "").strip()]
    current["model_base_url"] = str(current.get("model_base_url") or "http://127.0.0.1:1234")
    current["debug_enabled"] = bool(current.get("debug_enabled"))
    current["debug_token"] = str(current.get("debug_token") or "")
    stored = {
        "enabled": current["enabled"],
        "host": current["host"],
        "port": current["port"],
        "lan_access": current["lan_access"],
        "users_root": current["users_root"],
        "users_roots": current["users_roots"],
        "user_quota_bytes": current["user_quota_bytes"],
        "model_base_url": current["model_base_url"],
        "debug_enabled": current["debug_enabled"],
        "debug_token": _seal(root, current["debug_token"]),
        "database_url": _seal(root, str(current.get("database_url") or "")),
        "api_key": _seal(root, str(current.get("api_key") or "")),
    }
    _write(_path(root), stored)
    return current


def sync_from_plugin(state_dir: Path | str, values: dict[str, Any]) -> None:
    """Copy the bind flags the interface already edits into the core file."""
    from .listen import truthy

    patch: dict[str, Any] = {}
    if "server_mode" in values:
        patch["enabled"] = truthy(values.get("server_mode"))
    if values.get("host"):
        patch["host"] = str(values.get("host")).strip()
    if values.get("port") not in (None, ""):
        patch["port"] = values.get("port")
    if "lan_access" in values:
        patch["lan_access"] = truthy(values.get("lan_access"))
    if patch:
        save_server_settings(state_dir, patch)


def ensure_api_key(state_dir: Path | str) -> tuple[str, bool]:
    """Return the API key and whether it was just created."""
    import secrets

    current = load_server_settings(state_dir)
    if current.get("api_key"):
        return str(current["api_key"]), False
    key = secrets.token_urlsafe(24)
    save_server_settings(state_dir, {"api_key": key})
    return key, True
