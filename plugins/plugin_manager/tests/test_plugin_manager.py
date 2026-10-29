"""Plugin Manager plugin initializes itself through Kerniq's plugin manager."""

from __future__ import annotations

import asyncio
from pathlib import Path

from Kerniq.plugins.base import PluginContext
from Kerniq.plugins.manager import PluginManager
from Kerniq.tools.registry import ToolRegistry


def test_plugin_manager_discovers_and_loads():
    plugins_root = Path(__file__).resolve().parents[2]
    registry = ToolRegistry()
    manager = PluginManager(
        lambda: PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry)
    )

    async def run():
        await manager.discover_and_load(plugins_root)
        return manager.plugins.get("plugin_plugin_manager")

    plugin = asyncio.run(run())
    assert plugin is not None
    assert manager.manifests["plugin_plugin_manager"].plugin_id == "plugin_plugin_manager"
    assert "tools" in manager.manifests["plugin_plugin_manager"].capabilities
