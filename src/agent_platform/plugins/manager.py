"""Plugin discovery and lifecycle manager."""

from __future__ import annotations

import importlib.util
import logging
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import Plugin, PluginContext
from .manifest import PluginManifest, PluginStatus

logger = logging.getLogger(__name__)


def normalize_manifest_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Accept both flat manifests and nested [plugin] / [capabilities] tables."""
    if not isinstance(data, dict):
        return {}

    # Nested: [plugin] plugin_id = ...
    if "plugin" in data and isinstance(data["plugin"], dict):
        merged = dict(data["plugin"])
        for k, v in data.items():
            if k == "plugin":
                continue
            if k not in merged:
                merged[k] = v
        data = merged

    # capabilities as { tools = true } → ["tools"]
    caps = data.get("capabilities")
    if isinstance(caps, dict):
        data["capabilities"] = [k for k, v in caps.items() if v]
    elif caps is None:
        data["capabilities"] = []
    elif isinstance(caps, str):
        data["capabilities"] = [caps]

    return data


class PluginManager:
    def __init__(self, context_factory):
        self.context_factory = context_factory
        self.plugins: Dict[str, Plugin] = {}
        self.statuses: Dict[str, PluginStatus] = {}
        self.manifests: Dict[str, PluginManifest] = {}
        self.errors: Dict[str, str] = {}

    async def discover_and_load(self, plugins_dir: Path) -> None:
        if not plugins_dir.exists():
            logger.warning("Plugins directory %s does not exist.", plugins_dir)
            return
        for item in sorted(plugins_dir.iterdir()):
            if item.is_dir() and (item / "manifest.toml").exists():
                await self._load_plugin(item)

    async def _load_plugin(self, plugin_path: Path) -> None:
        plugin_key = plugin_path.name
        try:
            with open(plugin_path / "manifest.toml", "rb") as f:
                raw = tomllib.load(f)
            manifest_data = normalize_manifest_data(raw)
            manifest = PluginManifest(**manifest_data)
            pid = manifest.plugin_id
            self.manifests[pid] = manifest
            self.statuses[pid] = PluginStatus.DISCOVERED

            main_py = plugin_path / "main.py"
            if not main_py.exists():
                msg = f"Plugin {pid} missing main.py"
                logger.error(msg)
                self.statuses[pid] = PluginStatus.ERROR
                self.errors[pid] = msg
                return

            module_name = f"agent_platform_plugin_{plugin_path.name}"
            spec = importlib.util.spec_from_file_location(module_name, main_py)
            if spec is None or spec.loader is None:
                self.statuses[pid] = PluginStatus.ERROR
                self.errors[pid] = "Cannot create module spec"
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Prefer PluginImpl; fall back to first Plugin subclass
            plugin_class: Optional[Type[Plugin]] = getattr(module, "PluginImpl", None)
            if plugin_class is None:
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, Plugin)
                        and obj is not Plugin
                    ):
                        plugin_class = obj
                        break
            if plugin_class is None:
                msg = f"Plugin {pid}: no PluginImpl (or Plugin subclass) in main.py"
                logger.error(msg)
                self.statuses[pid] = PluginStatus.ERROR
                self.errors[pid] = msg
                return

            plugin_instance = plugin_class()
            context = self.context_factory()
            if await plugin_instance.initialize(context):
                self.plugins[pid] = plugin_instance
                self.statuses[pid] = PluginStatus.AVAILABLE
                logger.info("Plugin %s loaded successfully.", pid)
            else:
                msg = f"Plugin {pid} initialize() returned False"
                logger.error(msg)
                self.statuses[pid] = PluginStatus.ERROR
                self.errors[pid] = msg
        except Exception as e:
            logger.error(
                "Error loading plugin from %s: %s", plugin_path, e, exc_info=False
            )
            # Do not re-raise — one bad plugin must not kill UI / others
            self.errors[plugin_key] = str(e)
            if plugin_key not in self.statuses:
                self.statuses[plugin_key] = PluginStatus.ERROR

    async def shutdown_all(self) -> None:
        for plugin_id, plugin in list(self.plugins.items()):
            try:
                await plugin.shutdown()
                self.statuses[plugin_id] = PluginStatus.STOPPED
            except Exception as e:
                logger.error("Error shutting down plugin %s: %s", plugin_id, e)

    def get_plugin_status(self, plugin_id: str) -> Optional[PluginStatus]:
        return self.statuses.get(plugin_id)

    def list_plugins(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": pid,
                "status": status,
                "manifest": self.manifests.get(pid),
                "error": self.errors.get(pid),
            }
            for pid, status in self.statuses.items()
        ]
