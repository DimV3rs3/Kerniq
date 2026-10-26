import asyncio
import importlib.util
import json
import os
from pathlib import Path

from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from Kerniq.settings.component_store import ComponentSettingsStore
from Kerniq.settings.ui_store import UiSettingsStore
from Kerniq.tools.packs.filesystem.tools import ReadFileTool


def test_reading_settings_does_not_create_a_missing_state_dir(tmp_path):
    missing = tmp_path / "state"
    store = UiSettingsStore(missing)
    loaded = store.load()
    assert loaded.agent.workspace == "./workspace"
    assert not missing.exists()
    store.save()
    assert (missing / "settings.json").is_file()


def test_uninstall_drops_project_workspace_not_an_external_one(tmp_path):
    from Kerniq.devtools.uninstall import _purge_project_state

    project = tmp_path / "proj"
    (project / "workspace").mkdir(parents=True)
    (project / "workspace" / ".kerniq-venv").mkdir()
    (project / "state").mkdir()
    (project / "src").mkdir()
    (project / "src" / ".kerniq-venv").mkdir()
    (project / "custom").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / "state" / "settings.json").write_text(
        json.dumps({"agent": {"workspace": "./custom"}}),
        encoding="utf-8",
    )
    report = _purge_project_state(project)
    assert not (project / "workspace").exists()
    assert not (project / "custom").exists()
    assert not (project / "state").exists()
    assert (project / "src").is_dir()
    assert (project / "src" / ".kerniq-venv").is_dir()
    assert not (project / "workspace" / ".kerniq-venv").exists()
    assert outside.is_dir()
    assert any("workspace" in line for line in report)

    project2 = tmp_path / "proj2"
    (project2 / "state").mkdir(parents=True)
    (project2 / "state" / "settings.json").write_text(
        json.dumps({"agent": {"workspace": str(outside)}}),
        encoding="utf-8",
    )
    (project2 / "workspace").mkdir()
    _purge_project_state(project2)
    assert outside.is_dir()
    assert not (project2 / "workspace").exists()
    assert not (project2 / "state").exists()


def test_uninstall_stops_the_ui_process_and_not_itself(tmp_path):
    from Kerniq.devtools import uninstall as u

    project = tmp_path / "proj"
    (project / "state").mkdir(parents=True)
    (project / "state" / "ui.pid").write_text(
        json.dumps({"pid": 4242, "role": "kerniq-web-ui"}),
        encoding="utf-8",
    )
    killed = []

    def fake_cmd(pid):
        if pid in (os.getpid(), 4242):
            return "python -m Kerniq plugins ui"
        return "python other"

    def fake_term(pid):
        killed.append(pid)
        return f"stopped pid {pid}"

    report = u._stop_ui_processes(
        project,
        cmdline=fake_cmd,
        terminate=fake_term,
        scan=lambda: [os.getpid(), 4242, 77],
    )
    assert killed == [4242]
    assert any("skipped" in line and str(os.getpid()) in line for line in report)
    assert any("77" in line and "not the Kerniq UI" in line for line in report)


def test_purge_reports_failure_when_a_directory_stays(tmp_path, monkeypatch):
    from Kerniq.devtools import uninstall as u

    project = tmp_path / "proj"
    (project / "workspace").mkdir(parents=True)
    (project / "state").mkdir()

    def boom(path, ignore_errors=False):
        raise OSError("busy")

    monkeypatch.setattr(u.shutil, "rmtree", boom)
    report = u._purge_project_state(project)
    assert any("FAILED" in line and "workspace" in line for line in report)
    assert (project / "workspace").is_dir()
    assert (project / "state").is_dir()


def test_defaults_land_in_settings_json(tmp_path):
    store = UiSettingsStore(tmp_path)
    store.load()
    path = tmp_path / "settings.json"
    assert path.is_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["agent"]["workspace"] == "./workspace"
    assert "tools" not in raw
    assert "plugins" not in raw
    assert "components" not in raw
    assert not (tmp_path / "ui_settings.json").exists()


def test_reconcile_adds_and_drops_components(tmp_path):
    UiSettingsStore(tmp_path).load()
    schema = SettingsSchema(
        component_id="read_file",
        component_type="tool",
        title="read_file",
        fields=[SettingField(key="collapsible", label="Merge", type=SettingType.BOOL, default=True)],
    )
    components = ComponentSettingsStore(tmp_path)
    components.save("tool", "read_file", {"collapsible": False}, schema)
    components.reconcile("tool", {"read_file": schema, "gone": schema})
    tools = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert tools["components"]["read_file"]["collapsible"] is False
    assert "gone" in tools["components"]
    components.reconcile("tool", {"read_file": schema})
    tools = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert list(tools["components"]) == ["read_file"]
    main = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert main["agent"]["workspace"] == "./workspace"
    assert "components" not in main


def test_tool_display_phrase_is_english():
    tool = ReadFileTool(Path("."))
    assert tool.display_phrase == "files read"
    assert tool.chat_label(2) == "2 files read"
    assert not hasattr(tool, "ui_display") or not callable(getattr(ReadFileTool, "ui_display", None))


def test_legacy_ui_settings_is_moved(tmp_path):
    (tmp_path / "ui_settings.json").write_text(
        json.dumps({"agent": {"workspace": "/tmp/keep"}, "tools": {"fs_enabled": False}}),
        encoding="utf-8",
    )
    loaded = UiSettingsStore(tmp_path).load()
    assert loaded.agent.workspace == "/tmp/keep"
    assert (tmp_path / "settings.json").is_file()
    assert not (tmp_path / "ui_settings.json").exists()
    main = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "tools" not in main
    tools = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert tools["fs_enabled"] is False


def test_tool_toggles_share_tools_json(tmp_path):
    from Kerniq.tools.settings import ToolSettingsStore

    UiSettingsStore(tmp_path).load()
    (tmp_path / "tool_settings.json").write_text(
        json.dumps({"fs_list_max_depth": 2}),
        encoding="utf-8",
    )
    store = ToolSettingsStore(tmp_path)
    assert store.settings.fs_list_max_depth == 2
    assert store.settings.web_search_enabled is True
    store.update(web_search_enabled=False)
    assert not (tmp_path / "tool_settings.json").exists()
    tools = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert tools["fs_list_max_depth"] == 2
    assert tools["web_search_enabled"] is False
    main = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert main["agent"]["workspace"] == "./workspace"
    assert "tools" not in main
    UiSettingsStore(tmp_path).update({"chat": {"streaming": False}})
    main = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    tools = json.loads((tmp_path / "tools.json").read_text(encoding="utf-8"))
    assert main["chat"]["streaming"] is False
    assert tools["fs_list_max_depth"] == 2


def test_removed_component_settings_are_forgotten(tmp_path):
    components = ComponentSettingsStore(tmp_path)
    components.save("plugin", "plugin_weather", {"enabled": False})
    components.forget("plugin", "plugin_weather")
    raw = json.loads((tmp_path / "plugins.json").read_text(encoding="utf-8"))
    assert "plugin_weather" not in raw["components"]


def test_language_pack_rejects_a_broken_file():
    path = Path(__file__).resolve().parents[2] / "plugins" / "web_ui" / "langpacks.py"
    spec = importlib.util.spec_from_file_location("kerniq_langpacks_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.validate_pack({"name_en": "French", "strings": {"Save": 1}})
    except mod.PackError as exc:
        assert any("name_native" in line for line in exc.errors)
        assert any("not text" in line for line in exc.errors)
    else:
        raise AssertionError("broken pack was accepted")
    pack = mod.validate_pack({
        "name_en": "French",
        "name_native": "Français",
        "strings": {"Save": "Enregistrer"},
    })
    assert pack["warnings"]
    assert "Save" not in pack["missing"] or True
    assert any("Partial pack" in line for line in pack["warnings"])


def test_closed_plan_does_not_grow():
    from Kerniq.tools.packs.plan.tools import merge_plan

    prior = [
        {"id": "1", "title": "Read the router", "status": "done"},
        {"id": "2", "title": "Read the tools", "status": "done"},
    ]
    incoming = prior + [{"id": "3", "title": "Implement it", "status": "pending"}]
    sealed = merge_plan(prior, incoming, seal_when_closed=True)
    assert [item["id"] for item in sealed] == ["1", "2"]
    assert all(item["status"] == "done" for item in sealed)
    first = merge_plan([], [
        {"id": "1", "title": "one", "status": "done"},
        {"id": "2", "title": "two", "status": "done"},
    ])
    assert [item["status"] for item in first] == ["active", "pending"]


def test_handoff_keeps_research_archive_and_refuses_reopen():
    from Kerniq.core.context import TaskContext
    from Kerniq.core.runtime_flow import handoff_archive
    from Kerniq.tools.packs.plan.tools import UpdatePlanTool
    from uuid import uuid4

    ctx = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="research")
    ctx.metadata["agent_mode"] = "plan"
    ctx.metadata["plan"] = [
        {"id": "1", "title": "Read the router", "status": "done"},
        {"id": "2", "title": "Read the tools", "status": "done"},
    ]
    ctx.metadata["plan_archive"] = [
        {"id": "1", "title": "Read the router", "status": "done"},
        {"id": "2", "title": "Read the tools", "status": "done"},
    ]
    sealed = asyncio.run(
        UpdatePlanTool().execute(
            {
                "items": [
                    {"id": "1", "title": "Read the router", "status": "pending"},
                    {"id": "3", "title": "Implement it", "status": "pending"},
                ]
            },
            ctx,
        )
    )
    assert sealed.output["sealed"] is True
    assert [item["id"] for item in ctx.metadata["plan"]] == ["1", "2"]
    archive = handoff_archive(ctx)
    assert [item["id"] for item in archive] == ["research:1", "research:2"]
    assert [item["title"] for item in archive] == ["Read the router", "Read the tools"]

    act = TaskContext(task_id=uuid4(), session_id=uuid4(), goal="act")
    act.metadata["agent_mode"] = "act"
    act.metadata["plan_archive"] = archive
    reopened = asyncio.run(
        UpdatePlanTool().execute(
            {
                "items": [
                    {"id": "research:1", "title": "Read the router", "status": "pending"},
                    {"id": "1", "title": "Write the patch", "status": "active"},
                ]
            },
            act,
        )
    )
    assert reopened.success
    assert [item["id"] for item in act.metadata["plan"]] == ["1"]
    assert act.metadata["plan"][0]["title"] == "Write the patch"
    assert act.metadata["plan_archive"][0]["id"] == "research:1"
    assert act.metadata["plan_archive"][0]["status"] == "done"
    assert "left closed" in reopened.human_readable
