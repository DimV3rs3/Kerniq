"""Load tools that live inside a plugin folder.

A plugin is one directory. If it contains ``tools/__init__.py`` with
``create_tools(plugin)``, those tools are registered when the plugin loads.
They are not agent commands unless the plugin manifest says so:

    [tools]
    expose_to_agent = false
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)


def expose_to_agent(plugin_path: Path) -> bool:
    manifest = plugin_path / "manifest.toml"
    if not manifest.exists():
        return False
    try:
        with open(manifest, "rb") as handle:
            raw = tomllib.load(handle)
    except Exception:
        logger.warning("Could not read tools flag in %s", manifest, exc_info=False)
        return False
    block = raw.get("tools") if isinstance(raw, dict) else None
    if not isinstance(block, dict):
        return False
    return bool(block.get("expose_to_agent"))


def register_folder_tools(plugin, plugin_path: Path, context) -> None:
    init = Path(plugin_path) / "tools" / "__init__.py"
    if not init.exists():
        return
    module_name = f"Kerniq_plugin_{Path(plugin_path).name}_tools"
    spec = importlib.util.spec_from_file_location(module_name, init)
    if spec is None or spec.loader is None:
        logger.warning("Cannot load tools package in %s", plugin_path)
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("Plugin tools failed to import: %s", plugin_path)
        return
    factory = getattr(module, "create_tools", None)
    if not callable(factory):
        logger.warning("%s has tools/ but no create_tools(plugin)", plugin_path)
        return
    try:
        tools = list(factory(plugin) or [])
    except Exception:
        logger.exception("create_tools failed in %s", plugin_path)
        return
    expose = expose_to_agent(Path(plugin_path))
    for tool in tools:
        try:
            context.register_tool(tool, expose_to_agent=expose)
        except Exception:
            logger.exception("Could not register a tool from %s", plugin_path)
