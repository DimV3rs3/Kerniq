"""Build 24: plugin zips and VRAM parsers. Build 29: plugins extend the prompt themselves."""

import zipfile
from pathlib import Path

from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from Kerniq.models.system_info import parse_nvidia_query, parse_windows_vram_rows
from Kerniq.plugins.distribution import adopt_plugin_archives
from Kerniq.plugins.live import apply_model_tool_filters, drop_live, model_system_notes, note_live


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


def test_a_loaded_plugin_can_note_the_prompt_and_filter_tools():
    class Gate:
        def system_note(self, mode):
            return "GATE " + str(mode)

        def filter_model_tools(self, specs, mode, tools=None):
            return [spec for spec in specs if spec["function"]["name"] != "explode"]

    note_live("sample_gate", Gate())
    try:
        assert model_system_notes("act") == "GATE act"
        specs = [
            {"type": "function", "function": {"name": "explode"}},
            {"type": "function", "function": {"name": "read_file"}},
        ]
        kept = apply_model_tool_filters(specs, "act", {})
        assert [spec["function"]["name"] for spec in kept] == ["read_file"]
    finally:
        drop_live("sample_gate")
    assert model_system_notes("act") == ""
    assert apply_model_tool_filters([{"type": "function", "function": {"name": "explode"}}], "act", {})[0]["function"]["name"] == "explode"


def test_a_plugin_can_keep_its_own_language():
    schema = SettingsSchema(
        component_id="sample",
        component_type="plugin",
        title="Sample",
        translate=False,
        fields=[SettingField(key="enabled", label="Enabled", type=SettingType.BOOL, default=True)],
    )
    assert schema.to_public()["translate"] is False
    assert "translate" not in SettingsSchema(
        component_id="sample",
        component_type="plugin",
        title="Sample",
    ).to_public()


def test_vram_parsers_use_the_reported_numbers():
    total, used, name = parse_nvidia_query("RTX 3060, 12288, 2048")
    assert total == 12.0
    assert used == 2.0
    assert "RTX 3060" in name
    windows, label = parse_windows_vram_rows("Name|12884901888")
    assert windows == 12.0
    assert label == "Name"
