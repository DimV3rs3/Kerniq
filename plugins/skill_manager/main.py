"""Import Agent Skills and name the enabled ones in the system prompt.

The model sees names and descriptions only. skill_load reads the instructions.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from Kerniq.interfaces.settings_schema import SettingField, SettingType, SettingsSchema
from Kerniq.plugins.base import Plugin
from Kerniq.plugins.manifest import PluginManifest


def _engine():
    path = Path(__file__).resolve().parent / "engine.py"
    name = "kerniq_skill_manager_engine"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError("skill manager engine is missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="plugin_skill_manager",
            name="Skill Manager",
            version="1.0.0",
            api_version="1.0",
            manifest_version="1.0",
            entry_point="main.PluginImpl",
            description=(
                "Import Agent Skills (SKILL.md) from GitHub or a folder and offer them to the model."
            ),
            capabilities=["tools"],
            author="Kerniq",
            license="MIT",
            permissions=["network", "filesystem"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def settings_schema(self) -> SettingsSchema:
        return SettingsSchema(
            component_id="plugin_skill_manager",
            component_type="plugin",
            title="Skill Manager",
            fields=[
                SettingField(
                    key="inject_catalog",
                    label="Offer installed skills to the model",
                    type=SettingType.BOOL,
                    default=True,
                    group="prompt",
                    description=(
                        "Names and descriptions of enabled skills are added to the system prompt. "
                        "The instructions load only when the model calls skill_load."
                    ),
                ),
                SettingField(
                    key="include_project",
                    label="Include skills from the workspace",
                    type=SettingType.BOOL,
                    default=True,
                    group="prompt",
                    description=(
                        "Also read SKILL.md folders already in the workspace, such as .claude/skills, "
                        ".agents/skills, and skills. They are not copied."
                    ),
                ),
                SettingField(
                    key="max_skills",
                    label="Skills listed in the prompt",
                    type=SettingType.INT,
                    default=40,
                    minimum=1,
                    maximum=80,
                    group="prompt",
                    description="How many enabled skills to name in the prompt. The rest stay available through skill_list.",
                ),
                SettingField(
                    key="block_critical",
                    label="Block risky scripts",
                    type=SettingType.BOOL,
                    default=False,
                    group="prompt",
                    description=(
                        "Do not import a skill whose scripts use eval, exec, or pickle. "
                        "Other scripts are kept and only noted."
                    ),
                ),
                SettingField(
                    key="import_source",
                    label="Import from",
                    type=SettingType.STRING,
                    default="",
                    group="import",
                    description=(
                        "A GitHub URL, owner/repo, owner/repo/path, a local folder, a zip, or the text of a SKILL.md file."
                    ),
                ),
                SettingField(
                    key="replace_existing",
                    label="Replace existing",
                    type=SettingType.BOOL,
                    default=False,
                    group="import",
                    description="When on, an import replaces a skill that already has the same id.",
                ),
                SettingField(
                    key="search_query",
                    label="Search",
                    type=SettingType.STRING,
                    default="",
                    group="import",
                    description="Words, or owner/repo. Search looks on GitHub. It does not install anything.",
                ),
                SettingField(
                    key="search_hits",
                    label="Search results",
                    type=SettingType.TEXT,
                    default="",
                    group="import",
                    readonly=True,
                    description="Filled by Search GitHub.",
                ),
                SettingField(
                    key="skill_id",
                    label="Skill id",
                    type=SettingType.STRING,
                    default="",
                    group="library",
                    description="Installed id used by Remove, Turn on, and Turn off.",
                ),
                SettingField(
                    key="library",
                    label="Installed skills",
                    type=SettingType.TEXT,
                    default="",
                    group="library",
                    readonly=True,
                    description="Filled by Refresh list. Press Refresh after an import if this text is old.",
                ),
            ],
        )

    def actions(self) -> list:
        return [
            {"id": "import_skill", "label": "Import", "description": "Import the source above."},
            {"id": "search_skills", "label": "Search GitHub", "description": "Search without installing."},
            {"id": "refresh_library", "label": "Refresh list", "description": "Read skills from disk."},
            {"id": "enable_skill", "label": "Turn on", "description": "Offer this skill to the model."},
            {"id": "disable_skill", "label": "Turn off", "description": "Keep the skill, but do not offer it."},
            {"id": "remove_skill", "label": "Remove", "description": "Delete an imported skill. Workspace skills stay."},
        ]

    def _values(self, tool_context: Any) -> dict[str, Any]:
        if isinstance(tool_context, dict) and isinstance(tool_context.get("values"), dict):
            return tool_context["values"]
        return {}

    def _library_values(self, engine, extra: dict | None = None) -> dict[str, Any]:
        opts = engine.current_options()
        workspace = engine.workspace_dir() if opts.get("include_project", True) else None
        text = engine.format_library(engine.list_skills(engine.skills_root(), workspace=workspace))
        values = {"library": text}
        if extra:
            values.update(extra)
        return values

    async def run_action(self, action_id: str, tool_context: Any) -> dict[str, Any]:
        engine = _engine()
        values = self._values(tool_context)
        force = bool(values.get("replace_existing"))
        block = bool(values.get("block_critical"))
        if action_id == "import_skill":
            result = engine.import_source(
                str(values.get("import_source") or ""),
                force=force,
                block_critical=block,
            )
            payload = {
                "ok": bool(result.get("ok")),
                "message": result.get("message") or result.get("error") or "Import failed.",
                "summary": result.get("message") or result.get("error") or "Import failed.",
                "values": self._library_values(engine),
            }
            return payload
        if action_id == "search_skills":
            found = engine.search_github(str(values.get("search_query") or values.get("import_source") or ""))
            text = engine.format_search(found)
            count = len(found.get("repos") or []) if isinstance(found, dict) else 0
            if not found.get("ok"):
                short = text
            elif count:
                short = f"{count} repositories. The list is under Search results."
            else:
                short = "No repositories found."
            return {
                "ok": bool(found.get("ok")),
                "message": short,
                "summary": short,
                "values": self._library_values(engine, {"search_hits": text}),
            }
        if action_id == "refresh_library":
            text = self._library_values(engine)["library"]
            count = 0 if text.startswith("(no skills)") else text.count("\n") + 1
            short = f"{count} skill(s)."
            return {"ok": True, "message": short, "summary": short, "values": {"library": text}}
        if action_id in {"enable_skill", "disable_skill"}:
            skill_id = str(values.get("skill_id") or "").strip()
            result = engine.set_skill_enabled(
                skill_id,
                action_id == "enable_skill",
                workspace=engine.workspace_dir(),
            )
            message = result.get("message") or result.get("error") or "Could not update that skill."
            return {
                "ok": bool(result.get("ok")),
                "message": message,
                "summary": message,
                "values": self._library_values(engine),
            }
        if action_id == "remove_skill":
            result = engine.remove_skill(
                str(values.get("skill_id") or ""),
                confirm=True,
                workspace=engine.workspace_dir(),
            )
            message = result.get("message") or result.get("error") or "Could not remove that skill."
            return {
                "ok": bool(result.get("ok")),
                "message": message,
                "summary": message,
                "values": self._library_values(engine),
            }
        raise ValueError(f"Unknown action {action_id}")

    def system_note(self, mode: str) -> str:
        engine = _engine()
        opts = engine.current_options()
        if not opts.get("inject_catalog", True):
            return ""
        workspace = engine.workspace_dir() if opts.get("include_project", True) else None
        records = engine.list_skills(engine.skills_root(), workspace=workspace)
        return engine.render_system_note(records, max_skills=int(opts.get("max_skills") or 40))

    async def initialize(self, context) -> bool:
        try:
            engine = _engine()
            root = engine.skills_root()
            if root.is_dir():
                engine.adopt_skill_archives(root)
        except Exception:
            if context is not None and getattr(context, "logger", None):
                context.logger.info("skill archives were not adopted", exc_info=False)
        if context is not None and getattr(context, "logger", None):
            context.logger.info("Skill Manager initialized")
        return True

    async def shutdown(self) -> None:
        return None
