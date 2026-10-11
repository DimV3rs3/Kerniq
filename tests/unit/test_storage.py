"""Unit tests for JSON storage and config defaults."""

from __future__ import annotations

import asyncio

from Kerniq.storage.json_store import JsonStorage
from Kerniq.interfaces.storage import StorageValue


def test_json_storage_roundtrip(tmp_path):
    async def _run():
        store = JsonStorage(tmp_path)
        await store.put("k1", StorageValue(data={"hello": "world"}))
        val = await store.get("k1")
        assert val is not None
        assert val.data["hello"] == "world"
        keys = await store.list_keys()
        assert "k1" in keys
        await store.delete("k1")
        assert await store.get("k1") is None
        await store.close()

    asyncio.run(_run())


def test_config_defaults():
    from Kerniq.settings.schema import PlatformConfig

    cfg = PlatformConfig()
    assert cfg.models.default_provider == "lm_studio"
    assert cfg.runtime.max_iterations >= 10
    assert cfg.application.auto_install_deps is True
    assert cfg.tools.web_search_enabled is True
    assert cfg.ui.port == 8765
