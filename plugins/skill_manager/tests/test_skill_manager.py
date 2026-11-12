"""Skill Manager imports heterogeneous SKILL.md trees and keeps instructions unloaded."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _engine():
    name = "kerniq_skill_manager_engine"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, ROOT / "engine.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


PDF = """---
name: pdf
description: Use this skill whenever the user wants to do anything with PDF files.
license: Complete terms in LICENSE.txt
---

# PDF Processing Guide

Read REFERENCE.md for the long version.
"""

CLAUDE = """---
name: Commit Helper
description: >
  Write a commit message from the staged diff.
when_to_use: the user asks for a commit message
allowed-tools: Bash Read
metadata:
  author: example
disable-model-invocation: true
---

# Commit

Follow the repository style.
"""

BARE = """# Notes

Turn meeting notes into a short list.
"""


def test_frontmatter_accepts_official_and_claude_fields():
    engine = _engine()
    parsed = engine.parse_skill_text(PDF, folder_name="pdf")
    assert parsed["id"] == "pdf"
    assert parsed["description"].startswith("Use this skill")
    assert parsed["extras"]["license"].startswith("Complete terms")
    assert "REFERENCE.md" in parsed["body"]

    claude = engine.parse_skill_text(CLAUDE, folder_name="commit-helper")
    assert claude["id"] == "commit-helper"
    assert "commit message" in claude["description"]
    assert "Use when: the user asks" in claude["description"]
    assert claude["extras"]["allowed-tools"] == "Bash Read"
    assert "author=example" in claude["extras"]["metadata"]
    assert any("normalized" in item for item in claude["warnings"])

    bare = engine.parse_skill_text(BARE, folder_name="Meeting Notes")
    assert bare["id"] == "meeting-notes"
    assert "meeting notes" in bare["description"].lower()


def test_discover_finds_hidden_and_plain_layouts(tmp_path: Path):
    engine = _engine()
    _write(tmp_path / ".claude" / "skills" / "commit" / "SKILL.md", PDF.replace("name: pdf", "name: commit"))
    _write(tmp_path / "skills" / "pdf" / "skill.md", PDF)
    _write(tmp_path / ".agents" / "skills" / "brand" / "SKILL.md", BARE.replace("# Notes", "---\nname: brand\ndescription: Apply the brand.\n---\n\n# Brand"))
    _write(tmp_path / "node_modules" / "left" / "SKILL.md", PDF)
    _write(tmp_path / "docs" / "readme.md", "no skill")
    found = {path.name for path in engine.discover_skills(tmp_path)}
    assert found == {"commit", "pdf", "brand"}


def test_import_tree_subpath_zip_and_escape(tmp_path: Path):
    engine = _engine()
    repo = tmp_path / "repo"
    _write(repo / "skills" / "pdf" / "SKILL.md", PDF)
    _write(repo / "skills" / "pdf" / "references" / "REFERENCE.md", "long reference")
    _write(repo / "skills" / "pdf" / "scripts" / "extract.py", "print('ok')\n")
    _write(repo / ".claude" / "skills" / "commit" / "SKILL.md", CLAUDE)
    _write(repo / "skills" / "evil" / "SKILL.md", "---\nname: evil\ndescription: Do not load.\n---\n\nNo.\n")
    _write(repo / "skills" / "evil" / "scripts" / "bad.py", "eval('print(1)')\n")

    dest = tmp_path / "skills"
    one = engine.install_tree(repo, dest, subpath="pdf")
    assert one["ok"] is True
    assert [item["id"] for item in one["installed"]] == ["pdf"]
    assert (dest / "pdf" / "references" / "REFERENCE.md").read_text(encoding="utf-8") == "long reference"

    again = engine.install_tree(repo, dest, subpath="skills/pdf")
    assert again["ok"] is False
    assert "Already installed" in again["error"]

    replaced = engine.install_tree(repo, dest, subpath=".claude/skills/commit", force=True)
    assert replaced["ok"] is True
    assert replaced["installed"][0]["id"] == "commit-helper"

    blocked = engine.install_tree(repo, dest, subpath="skills/evil", block_critical=True)
    assert blocked["ok"] is False
    assert "eval" in blocked["error"]

    allowed = engine.install_tree(repo, dest, subpath="skills/evil", block_critical=False)
    assert allowed["ok"] is True
    meta = json.loads((dest / "evil" / ".kerniq-skill.json").read_text(encoding="utf-8"))
    assert meta["risk"] == "critical"

    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("pack/SKILL.md", "---\nname: packed\ndescription: From a zip.\n---\n\n# Packed\n")
        handle.writestr("../escaped-skill.txt", "nope")
    outside = tmp_path.parent / "escaped-skill.txt"
    if outside.exists():
        outside.unlink()
    slipped = engine.import_source(str(archive), dest)
    assert slipped["ok"] is False
    assert not outside.exists()

    clean = tmp_path / "clean.zip"
    with zipfile.ZipFile(clean, "w") as handle:
        handle.writestr("Outer/packed/SKILL.md", "---\nname: packed\ndescription: From a zip.\n---\n\n# Packed\n")
        handle.writestr("Outer/packed/assets/template.md", "hello")
    imported = engine.import_source(str(clean), dest)
    assert imported["ok"] is True
    assert (dest / "packed" / "assets" / "template.md").is_file()


def test_paste_project_skills_and_prompt(tmp_path: Path, monkeypatch):
    engine = _engine()
    dest = tmp_path / "installed"
    monkeypatch.setenv("KERNIQ_SKILLS", str(dest))
    pasted = engine.import_source("---\nname: pasted\ndescription: Pasted from chat.\n---\n\nDo the thing.\n", dest)
    assert pasted["ok"] is True

    workspace = tmp_path / "workspace"
    _write(
        workspace / ".agents" / "skills" / "review" / "SKILL.md",
        "---\nname: review\ndescription: Review a diff for bugs.\n---\n\nRead the diff first.\n",
    )
    _write(workspace / ".agents" / "skills" / "review" / "references" / "bar.md", "rubric")
    records = engine.list_skills(dest, workspace=workspace)
    ids = {record["id"]: record["origin"] for record in records}
    assert ids["pasted"] == "installed"
    assert ids["review"] == "project"

    note = engine.render_system_note(records, max_skills=40)
    assert "skill_load" in note
    assert "- pasted:" in note
    assert "- review (in the workspace):" in note
    assert "Read the diff" not in note

    loaded = engine.load_skill("review", root=dest, workspace=workspace)
    assert loaded["ok"] is True
    assert "Read the diff first." in loaded["message"]
    assert "references/bar.md" in loaded["message"]
    assert "does not grant tools" not in loaded["message"]

    read = engine.read_skill_file("review", "references/bar.md", root=dest, workspace=workspace)
    assert read["ok"] is True
    assert "rubric" in read["message"]
    escaped = engine.read_skill_file("review", "../SKILL.md", root=dest, workspace=workspace)
    assert escaped["ok"] is False
    outside = engine.read_skill_file("pasted", "/etc/passwd", root=dest, workspace=workspace)
    assert outside["ok"] is False

    off = engine.set_skill_enabled("review", False, dest, workspace=workspace)
    assert off["ok"] is True
    quiet = engine.render_system_note(engine.list_skills(dest, workspace=workspace), max_skills=40)
    assert "- review " not in quiet
    assert "turned off" in quiet

    removed = engine.remove_skill("review", confirm=True, skills_dir=dest, workspace=workspace)
    assert removed["ok"] is False
    assert (workspace / ".agents" / "skills" / "review" / "SKILL.md").is_file()
    gone = engine.remove_skill("pasted", confirm=False, skills_dir=dest, workspace=workspace)
    assert gone["ok"] is False
    gone = engine.remove_skill("pasted", confirm=True, skills_dir=dest, workspace=workspace)
    assert gone["ok"] is True
    assert not (dest / "pasted").exists()


def test_urls_and_many_skills_cap_message(tmp_path: Path):
    engine = _engine()
    assert engine.parse_import_source("anthropics/skills")["repo"] == "skills"
    blob = engine.parse_import_source("https://github.com/anthropics/skills/blob/main/skills/pdf/SKILL.md")
    assert blob["owner"] == "anthropics"
    assert blob["ref"] == "main"
    assert blob["subpath"] == "skills/pdf/SKILL.md"
    tree = engine.parse_import_source("https://github.com/anthropics/skills/tree/main/skills/pdf")
    assert tree["subpath"] == "skills/pdf"
    raw = engine.parse_import_source("https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md")
    assert raw["kind"] == "github"
    assert raw["subpath"].endswith("SKILL.md")
    nested = engine.parse_import_source("anthropics/skills/skills/pdf")
    assert nested["subpath"] == "skills/pdf"

    repo = tmp_path / "many"
    for index in range(3):
        _write(
            repo / "skills" / f"s{index}" / "SKILL.md",
            f"---\nname: s{index}\ndescription: Skill {index}.\n---\n\nBody {index}.\n",
        )
    engine.MAX_INSTALL = 2
    try:
        result = engine.install_tree(repo, tmp_path / "out")
    finally:
        engine.MAX_INSTALL = 60
    assert result["ok"] is True
    assert len(result["installed"]) == 2
    assert "left behind" in result["message"]


def test_tools_are_offered_and_round_trip(tmp_path: Path, monkeypatch):
    engine = _engine()
    monkeypatch.setenv("KERNIQ_SKILLS", str(tmp_path / "skills"))
    monkeypatch.setattr(engine, "workspace_dir", lambda: None)
    monkeypatch.setattr(engine, "current_options", lambda: {
        "inject_catalog": True,
        "include_project": False,
        "max_skills": 40,
        "block_critical": False,
        "replace_existing": False,
    })
    spec = importlib.util.spec_from_file_location(
        "kerniq_skill_manager_tools",
        ROOT / "tools" / "__init__.py",
    )
    tools_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools_mod)
    tools = {tool.name: tool for tool in tools_mod.create_tools(None)}
    assert set(tools) == {
        "skill_list", "skill_load", "skill_read", "skill_search", "skill_import", "skill_manage",
    }
    assert tools["skill_load"].plan_membership_default() is True
    assert tools["skill_import"].plan_membership_default() is False
    assert tools["skill_import"].risk_level == "medium"

    imported = asyncio.run(tools["skill_import"].execute({
        "source": "---\nname: demo\ndescription: Demo skill for a list.\n---\n\nOpen NOTES.md.\n",
    }, None))
    assert imported.success is True
    assert "demo" in imported.human_readable

    listed = asyncio.run(tools["skill_list"].execute({}, None))
    assert "demo" in listed.human_readable
    loaded = asyncio.run(tools["skill_load"].execute({"id": "demo"}, None))
    assert "Open NOTES.md." in loaded.human_readable
    assert "Demo skill" in loaded.human_readable

    main_spec = importlib.util.spec_from_file_location("kerniq_skill_manager_main", ROOT / "main.py")
    main_mod = importlib.util.module_from_spec(main_spec)
    main_spec.loader.exec_module(main_mod)
    plugin = main_mod.PluginImpl()
    note = plugin.system_note("act")
    assert "- demo:" in note
    assert "Open NOTES.md" not in note

    from Kerniq.plugins.distribution import KIT_IDS
    from Kerniq.plugins.folder_tools import register_folder_tools
    from Kerniq.plugins.base import PluginContext
    from Kerniq.tools.registry import ToolRegistry

    assert "plugin_skill_manager" in KIT_IDS
    registry = ToolRegistry()
    register_folder_tools(
        plugin,
        ROOT,
        PluginContext(logger=None, config=None, event_bus=None, tool_registry=registry),
    )
    offered = {spec["function"]["name"] for spec in registry.get_tools_for_model()}
    assert "skill_load" in offered
    assert "skill_import" in offered
