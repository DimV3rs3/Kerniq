"""Three state files. Kerniq reads and writes them; nothing else owns the format.

- state/settings.json — agent, API, prompt, chat
- state/tools.json — tool toggles and per-tool values
- state/plugins.json — per-plugin values

Defaults are written the first time a file is created. A later change from
the console or the shell replaces those values in the same file. An older
single settings.json is split once, then the extra keys are removed from it.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

MAIN_FILE = "settings.json"
TOOLS_FILE = "tools.json"
PLUGINS_FILE = "plugins.json"
LEGACY_MAIN = "ui_settings.json"
LEGACY_TOOLS = "tool_settings.json"
_LOCK = threading.RLock()


def state_root(state_dir: Path | str, *, create: bool = False) -> Path:
    """The project state directory. Relative paths stay on the project root.

    Reading must not create the directory. A deleted state/ stays deleted
    until something actually writes a file.
    """
    from ..devtools.paths import anchored_dir

    root = anchored_dir(state_dir)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def state_file(state_dir: Path | str, name: str) -> Path:
    return state_root(state_dir) / name


def settings_path(state_dir: Path | str) -> Path:
    return state_file(state_dir, MAIN_FILE)


def read_state_file(state_dir: Path | str, name: str) -> dict[str, Any]:
    root = state_root(state_dir)
    with _LOCK:
        _import_legacy_main(root)
        _ensure_split(root)
        return _read(root / name)


def write_state_file(state_dir: Path | str, name: str, data: dict[str, Any]) -> None:
    path = state_file(state_dir, name)
    with _LOCK:
        _write(path, data)


def read_settings_file(state_dir: Path | str) -> dict[str, Any]:
    return read_state_file(state_dir, MAIN_FILE)


def write_settings_file(state_dir: Path | str, data: dict[str, Any]) -> None:
    cleaned = dict(data)
    for key in ("tools", "plugins", "components"):
        cleaned.pop(key, None)
    write_state_file(state_dir, MAIN_FILE, cleaned)


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _import_legacy_main(root: Path) -> None:
    path = root / MAIN_FILE
    legacy = root / LEGACY_MAIN
    if path.exists() or not legacy.is_file():
        return
    data = _read(legacy)
    _write(path, data)
    try:
        legacy.unlink()
    except OSError:
        pass


def _ensure_split(root: Path) -> None:
    """Move tool and plugin blocks out of the main file. Safe to call twice."""
    main_path = root / MAIN_FILE
    main = _read(main_path)
    tools = _read(root / TOOLS_FILE)
    plugins = _read(root / PLUGINS_FILE)
    changed_main = False

    block = main.get("tools")
    if isinstance(block, dict):
        for key, value in block.items():
            tools.setdefault(key, value)
        main.pop("tools", None)
        changed_main = True

    block = main.get("plugins")
    if isinstance(block, dict):
        enabled = block.get("enabled")
        if isinstance(enabled, dict):
            bucket = plugins.setdefault("components", {})
            if not isinstance(bucket, dict):
                bucket = {}
                plugins["components"] = bucket
            for plugin_id, flag in enabled.items():
                current = bucket.get(plugin_id)
                if not isinstance(current, dict):
                    current = {}
                    bucket[plugin_id] = current
                current.setdefault("enabled", bool(flag))
        main.pop("plugins", None)
        changed_main = True

    components = main.get("components")
    if isinstance(components, dict):
        _merge_components(tools, components.get("tool"))
        _merge_components(plugins, components.get("plugin"))
        main.pop("components", None)
        changed_main = True

    legacy_tools = root / LEGACY_TOOLS
    if legacy_tools.is_file():
        data = _read(legacy_tools)
        for key, value in data.items():
            if key != "components":
                tools.setdefault(key, value)
        try:
            legacy_tools.unlink()
        except OSError:
            pass

    if _absorb_dir(root / "tools", tools):
        pass
    if _absorb_dir(root / "plugins", plugins):
        pass

    if tools and (changed_main or not (root / TOOLS_FILE).is_file() or legacy_tools.exists() is False):
        if tools != _read(root / TOOLS_FILE):
            _write(root / TOOLS_FILE, tools)
    elif tools != _read(root / TOOLS_FILE) and tools:
        _write(root / TOOLS_FILE, tools)
    if plugins and plugins != _read(root / PLUGINS_FILE):
        _write(root / PLUGINS_FILE, plugins)
    if changed_main:
        _write(main_path, main)


def _merge_components(doc: dict[str, Any], incoming: Any) -> None:
    if not isinstance(incoming, dict):
        return
    bucket = doc.get("components")
    if not isinstance(bucket, dict):
        bucket = {}
        doc["components"] = bucket
    for key, value in incoming.items():
        if isinstance(value, dict):
            bucket.setdefault(key, value)


def _absorb_dir(folder: Path, doc: dict[str, Any]) -> bool:
    """Copy state/tools/<id>.json or state/plugins/<id>.json into the one file."""
    if not folder.is_dir():
        return False
    bucket = doc.get("components")
    if not isinstance(bucket, dict):
        bucket = {}
        doc["components"] = bucket
    moved = False
    for path in folder.glob("*.json"):
        if path.stem in bucket:
            continue
        data = _read(path)
        if not data:
            continue
        bucket[path.stem] = data
        moved = True
        try:
            path.unlink()
        except OSError:
            pass
    return moved
