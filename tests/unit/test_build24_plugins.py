"""Build 24: plugin zips, the multi-agent tool gate, and VRAM parsers."""

import zipfile
from pathlib import Path

from Kerniq.core.delegation import allow_tool
from Kerniq.models.system_info import parse_nvidia_query, parse_windows_vram_rows
from Kerniq.plugins.distribution import adopt_plugin_archives


_MANIFEST = """\
plugin_id = "{plugin_id}"
name = "Sample"
version = "1.0.0"
api_version = "1.0"
manifest_version = "1.0"
entry_point = "main.PluginImpl"
description = "sample"
"""
_MAIN = "class PluginImpl:\n    pass\n"


def _zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)


def test_a_plugin_zip_is_installed_and_the_archive_is_deleted(tmp_path: Path):
    archive = tmp_path / "sample.zip"
    _zip(archive, {
        "manifest.toml": _MANIFEST.format(plugin_id="sample_plug"),
        "main.py": _MAIN,
    })
    results = adopt_plugin_archives(tmp_path)
    assert results and results[0]["ok"] is True
    assert not archive.exists()
    assert (tmp_path / "sample_plug" / "manifest.toml").is_file()
    assert (tmp_path / "sample_plug" / "main.py").is_file()


def test_a_zip_that_is_not_a_plugin_is_left_alone(tmp_path: Path):
    archive = tmp_path / "notes.zip"
    _zip(archive, {"readme.txt": "not a plugin"})
    results = adopt_plugin_archives(tmp_path)
    assert archive.is_file()
    assert results[0]["kept"] is True
    assert not any(item.is_dir() and (item / "manifest.toml").is_file() for item in tmp_path.iterdir())


def test_a_double_nested_plugin_zip_is_installed(tmp_path: Path):
    archive = tmp_path / "wrapped.zip"
    _zip(archive, {
        "Outer/nested_plug/manifest.toml": _MANIFEST.format(plugin_id="nested_plug"),
        "Outer/nested_plug/main.py": _MAIN,
    })
    results = adopt_plugin_archives(tmp_path)
    assert results[0]["ok"] is True
    assert not archive.exists()
    assert (tmp_path / "nested_plug" / "main.py").read_text(encoding="utf-8") == _MAIN


def test_a_parent_path_in_a_zip_does_not_escape(tmp_path: Path):
    archive = tmp_path / "bad.zip"
    outside = tmp_path.parent / "escaped-from-plugin-zip.txt"
    if outside.exists():
        outside.unlink()
    _zip(archive, {
        "../escaped-from-plugin-zip.txt": "nope",
        "manifest.toml": _MANIFEST.format(plugin_id="bad_plug"),
        "main.py": _MAIN,
    })
    results = adopt_plugin_archives(tmp_path)
    assert archive.is_file()
    assert results[0]["kept"] is True
    assert not outside.exists()
    assert not (tmp_path / "bad_plug").exists()


def test_allow_tool_keeps_readonly_and_run_agents_in_act_mode():
    assert allow_tool("write_file", "high", mode="act", enabled=False) is True
    assert allow_tool("run_agents", "medium", mode="act", enabled=False) is True
    assert allow_tool("run_agents", "medium", mode="plan", enabled=True) is False
    assert allow_tool("read_file", "low", mode="plan", enabled=True) is True
    assert allow_tool("write_file", "high", mode="act", enabled=True) is False
    assert allow_tool("update_plan", "low", mode="act", enabled=True) is False
    assert allow_tool("read_file", "low", mode="act", enabled=True) is True
    assert allow_tool("run_agents", "medium", mode="act", enabled=True) is True


def test_vram_parsers_use_the_reported_numbers():
    total, used, name = parse_nvidia_query("RTX 3060, 12288, 2048")
    assert total == 12.0
    assert used == 2.0
    assert "RTX 3060" in name
    windows, label = parse_windows_vram_rows("Name|12884901888")
    assert windows == 12.0
    assert label == "Name"
