"""Attach one plugin to another, only where the host allows it.

A host lists slots from ``extension_slots()``. Another plugin offers a
contribution with ``contributions()``. The contribution is kept only when
``host`` matches a loaded plugin and ``slot`` is one of that host's slots.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import tomllib
from pathlib import Path
from typing import Any

from .base import Plugin

logger = logging.getLogger(__name__)


def _plugin_class(plugin_path: Path):
    main_py = plugin_path / "main.py"
    if not main_py.exists():
        return None
    module_name = f"Kerniq_plugin_ext_{plugin_path.name}"
    spec = importlib.util.spec_from_file_location(module_name, main_py)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    plugin_class = getattr(module, "PluginImpl", None)
    if plugin_class is None:
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                plugin_class = obj
                break
    return plugin_class


def scan_extensions(plugins_dir: Path) -> list[dict[str, Any]]:
    root = Path(plugins_dir)
    if not root.is_dir():
        return []
    slots: dict[str, set[str]] = {}
    offers: list[dict[str, Any]] = []
    for item in sorted(root.iterdir()):
        if not item.is_dir() or not (item / "manifest.toml").exists():
            continue
        try:
            with open(item / "manifest.toml", "rb") as handle:
                raw = tomllib.load(handle)
            plugin_block = raw.get("plugin") if isinstance(raw.get("plugin"), dict) else raw
            plugin_id = str((plugin_block or {}).get("plugin_id") or item.name)
            cls = _plugin_class(item)
            if cls is None:
                continue
            inst = cls()
            declared = inst.extension_slots() or []
            slots[plugin_id] = {str(slot) for slot in declared if str(slot)}
            for raw_offer in inst.contributions() or []:
                if not isinstance(raw_offer, dict):
                    continue
                row = dict(raw_offer)
                row.setdefault("plugin_id", plugin_id)
                offers.append(row)
        except Exception:
            logger.info("extension scan skipped %s", item.name, exc_info=True)
    kept: list[dict[str, Any]] = []
    for row in offers:
        host = str(row.get("host") or "")
        slot = str(row.get("slot") or "")
        if not host or not slot or slot not in slots.get(host, set()):
            continue
        kept.append({
            "host": host,
            "slot": slot,
            "id": str(row.get("id") or ""),
            "label": str(row.get("label") or row.get("id") or "Extension"),
            "icon": str(row.get("icon") or "puzzle"),
            "plugin_id": str(row.get("plugin_id") or ""),
        })
    return kept
