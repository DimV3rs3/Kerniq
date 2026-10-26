"""Which address the single Kerniq process listens on.

A saved public host or server mode wins over the loopback default. The
schema default ``127.0.0.1`` must not hide ``0.0.0.0`` written in config.
"""

from __future__ import annotations

import os
from typing import Any, Mapping, Optional

_LOOPBACK = {"", "127.0.0.1", "localhost", "::1"}


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def is_public_bind(host: str) -> bool:
    return _text(host) not in _LOOPBACK


def _port(*candidates: Any) -> int:
    for candidate in candidates:
        if candidate is None or candidate == "":
            continue
        try:
            port = int(candidate)
        except (TypeError, ValueError):
            continue
        if 1 <= port <= 65535:
            return port
    return 8765


def resolve_listen(
    *,
    config_host: str = "127.0.0.1",
    config_port: int = 8765,
    plugin: Optional[Mapping[str, Any]] = None,
    core: Optional[Mapping[str, Any]] = None,
    cli_host: Optional[str] = None,
    cli_port: Optional[int] = None,
    env: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Return host, port, server_mode, and lan_access for this process.

    Explicit ``--host`` wins. Otherwise the first public address among the
    plugin settings, the core server file, and platform config is used.
    A loopback value that was only filled in as a default does not override
    ``0.0.0.0``. Server mode and LAN access force a public bind.
    """
    plugin = dict(plugin or {})
    core = dict(core or {})
    env_map = env if env is not None else os.environ
    plugin_host = _text(plugin.get("host"))
    core_host = _text(core.get("host"))
    cfg_host = _text(config_host) or "127.0.0.1"
    env_host = _text(env_map.get("KERNIQ_BIND") or env_map.get("KERNIQ_HOST"))
    server = (
        truthy(plugin.get("server_mode"))
        or truthy(core.get("enabled"))
        or truthy(env_map.get("KERNIQ_SERVER_MODE"))
    )
    lan = truthy(plugin.get("lan_access")) or truthy(core.get("lan_access"))
    port = _port(cli_port, env_map.get("KERNIQ_PORT"), plugin.get("port"), core.get("port"), config_port)

    explicit = bool(_text(cli_host))
    if _text(cli_host):
        host = _text(cli_host)
    elif env_host:
        host = env_host
    else:
        host = ""
        for candidate in (plugin_host, core_host, cfg_host):
            if is_public_bind(candidate):
                host = candidate
                break
        if not host:
            host = plugin_host or core_host or cfg_host or "127.0.0.1"

    if (server or lan) and not explicit and not is_public_bind(host):
        host = "0.0.0.0"
    return {
        "host": host or "127.0.0.1",
        "port": port,
        "server_mode": bool(server),
        "lan_access": bool(lan or host in {"0.0.0.0", "::"}),
    }
