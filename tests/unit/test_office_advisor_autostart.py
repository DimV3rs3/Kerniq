"""Office documents, local model advice, and UI autostart."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from Kerniq.plugins.base import PluginContext
from Kerniq.plugins.distribution import inspect_plugin, install_tree
from Kerniq.plugins.manager import PluginManager
from Kerniq.tools.filesystem import FileSystemTools
from Kerniq.tools.registry import ToolRegistry


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_office_roundtrip_and_plain_text_refusal(tmp_path):
    engine = _load(Path(__file__).resolve().parents[2] / "catalog" / "Kerniq-office" / "engine.py", "office_engine_test")
    docx = tmp_path / "note.docx"
    created = engine.create_document(docx, {
        "paragraphs": [
            {"text": "Title", "style": "Heading1", "font": "Calibri", "size_pt": 18, "bold": True},
            {"text": "Body", "font": "Times New Roman", "size_pt": 12},
        ],
        "tables": [{"cells": [["A", "B"], ["C", "D"]]}],
    })
    assert created["tables"][0]["n"] == 1
    assert created["tables"][0]["rows"] == 2 and created["tables"][0]["cols"] == 2
    assert created["paragraphs"][0]["style"] == "Heading1"
    assert created["paragraphs"][0]["font"] == "Calibri"
    assert created["paragraphs"][0]["size_pt"] == 18
    edited = engine.edit_document(docx, [
        {"op": "set_cell", "table": 1, "row": 2, "col": 2, "text": "Z", "font": "Calibri", "size_pt": 14, "bold": True},
        {"op": "set_paragraph", "index": 2, "text": "Changed", "style": "Heading2", "font": "Calibri", "size_pt": 13},
        {"op": "add_paragraph", "text": "After", "style": "Normal"},
    ])
    assert edited["tables"][0]["cells"][1][1] == "Z"
    assert edited["paragraphs"][1]["text"] == "Changed"
    assert edited["paragraphs"][1]["style"] == "Heading2"
    assert any(item["text"] == "After" for item in edited["paragraphs"])

    odt = tmp_path / "note.odt"
    engine.create_document(odt, {"paragraphs": [{"text": "Hi", "style": "Title", "font": "Liberation Sans", "size_pt": 20}], "tables": [{"cells": [["1"]]}]})
    seen = engine.read_document(odt)
    assert seen["tables"][0]["n"] == 1
    assert seen["paragraphs"][0]["style"] == "Title"
    changed = engine.edit_document(odt, [{"op": "set_cell", "table": 1, "row": 1, "col": 1, "text": "9", "bold": True}])
    assert changed["tables"][0]["cells"][0][0] == "9"

    xlsx = tmp_path / "book.xlsx"
    engine.create_document(xlsx, {"sheets": [{"name": "Sheet1", "cells": [{"row": 1, "col": 1, "value": "Name", "bold": True, "font": "Calibri", "size_pt": 12}]}]})
    sheet = engine.edit_document(xlsx, [{"op": "set_sheet_cell", "sheet": "Sheet1", "row": 2, "col": 1, "value": 5}])
    values = {(cell["row"], cell["col"]): cell["value"] for cell in sheet["sheets"][0]["cells"]}
    assert values[(1, 1)] == "Name"
    assert values[(2, 1)] == 5

    pptx = tmp_path / "deck.pptx"
    engine.create_document(pptx, {"slides": [{"title": "One", "body": "Hello", "font": "Calibri"}]})
    slides = engine.edit_document(pptx, [{"op": "add_slide", "title": "Two", "body": "More"}])
    assert [item["title"] for item in slides["slides"]] == ["One", "Two"]

    ods = tmp_path / "book.ods"
    engine.create_document(ods, {"sheets": [{"name": "Data", "cells": [{"row": 1, "col": 2, "value": "q"}]}]})
    ods_row = engine.read_document(ods)
    assert ods_row["sheets"][0]["cells"][0]["value"] == "q"
    odp = tmp_path / "deck.odp"
    engine.create_document(odp, {"slides": [{"title": "Slide", "body": "Body"}]})
    assert engine.read_document(odp)["slides"][0]["title"] == "Slide"

    try:
        engine.create_document(tmp_path / "old.doc", {})
    except engine.OfficeError as exc:
        assert "legacy" in str(exc).lower() or ".docx" in str(exc)
    else:
        raise AssertionError("legacy doc was accepted")

    fs = FileSystemTools(str(tmp_path))
    reg = ToolRegistry()
    for tool in fs.get_tools():
        reg.register_tool(tool)

    async def refuse():
        created_file = await reg.get_tool("create_file").execute({"path": "bad.docx", "content": "x", "tool_call_id": "1"}, None)
        assert created_file.status == "error"
        assert "office" in created_file.human_readable.lower()
        assert not (tmp_path / "bad.docx").exists()

    asyncio.run(refuse())


def test_model_advice_presets_stay_local():
    engine = _load(Path(__file__).resolve().parents[2] / "catalog" / "Kerniq-model-advisor" / "engine.py", "advisor_engine_test")
    system = {
        "os": "Linux",
        "arch": "x86_64",
        "cpu_count": 8,
        "memory_total_gb": 32,
        "memory_available_gb": 20,
        "vram_total_gb": 8,
        "has_gpu_hint": True,
    }
    balance = engine.advise("balance", system=system)
    performance = engine.advise("performance", system=system, models=["qwen2.5-7b-instruct-q4_k_m", "llama-3.1-70b-q4_k_m"])
    context = engine.advise("context", system=system, model="qwen2.5-7b-instruct-q5_k_m-32k")
    assert balance["local_only"] is True and balance["sent"] is False
    assert balance["recommendation"]["where"] == "vram"
    assert performance["recommendation"]["params_b"] == 7
    assert context["recommendation"]["context"] >= 4096
    parsed = engine.parse_model("mixtral-8x7b-instruct-q4")
    assert parsed["params_b"] == 56
    try:
        engine.advise("fast", system=system)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown preset was accepted")


def test_catalog_plugins_are_offered(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    assert inspect_plugin(repo / "catalog" / "Kerniq-office")["standalone"] is True
    assert inspect_plugin(repo / "catalog" / "Kerniq-model-advisor")["standalone"] is True
    assert install_tree(repo / "catalog" / "Kerniq-office", plugins_dir=tmp_path)["ok"] is True
    assert install_tree(repo / "catalog" / "Kerniq-model-advisor", plugins_dir=tmp_path)["ok"] is True

    async def go():
        registry = ToolRegistry()
        manager = PluginManager(lambda: PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry))
        await manager.discover_and_load(tmp_path)
        offered = {spec["function"]["name"] for spec in registry.get_tools_for_model()}
        assert {"office_inspect", "office_read", "office_create", "office_edit", "model_advice"} <= offered
        await manager.shutdown_all()

    asyncio.run(go())


def test_autostart_writes_only_the_fake_home(tmp_path):
    from Kerniq.devtools.autostart import configure, current

    project = tmp_path / "proj"
    (project / "plugins").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='kerniq'\n", encoding="utf-8")
    cases = (
        ("Windows", "AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Kerniq UI.vbs"),
        ("Darwin", "Library/LaunchAgents/com.kerniq.ui.plist"),
        ("Linux", ".config/autostart/kerniq-ui.desktop"),
    )
    for system, relative in cases:
        home = tmp_path / system
        home.mkdir()
        turned_on = configure(True, project=project, home=home, system=system, invoke=False)
        assert turned_on["ok"] is True
        assert turned_on["enabled"] is True
        assert (home / relative).is_file()
        assert "next time you sign in" in turned_on["message"]
        assert current(project=project, home=home, system=system)["enabled"] is True
        turned_off = configure(False, project=project, home=home, system=system, invoke=False)
        assert turned_off["enabled"] is False
        assert not (home / relative).exists()
        assert current(project=project, home=home, system=system)["enabled"] is False
