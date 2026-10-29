"""Web UI plugin initializes itself through Kerniq's plugin manager."""

from __future__ import annotations

import asyncio
from pathlib import Path

from Kerniq.plugins.base import PluginContext
from Kerniq.plugins.manager import PluginManager
from Kerniq.tools.registry import ToolRegistry


def test_web_ui_discovers_and_loads():
    plugins_root = Path(__file__).resolve().parents[2]
    registry = ToolRegistry()
    manager = PluginManager(
        lambda: PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry)
    )

    async def run():
        await manager.discover_and_load(plugins_root)
        return manager.plugins.get("plugin_web_ui")

    plugin = asyncio.run(run())
    assert plugin is not None
    assert manager.manifests["plugin_web_ui"].plugin_id == "plugin_web_ui"
    assert "ui" in manager.manifests["plugin_web_ui"].capabilities
