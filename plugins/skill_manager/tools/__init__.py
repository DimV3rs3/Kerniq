"""Tools the model uses to find, import, and read Agent Skills."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

from Kerniq.interfaces.tools import Tool, ToolResult


def _engine():
    path = Path(__file__).resolve().parent.parent / "engine.py"
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


class _SkillTool(Tool):
    def __init__(self, plugin=None):
        self._plugin = plugin

    def _done(self, arguments: Dict[str, Any], text: str, output: Any = None) -> ToolResult:
        return ToolResult(
            tool_call_id=str(arguments.get("tool_call_id") or ""),
            tool_id=self.tool_id,
            status="success",
            success=True,
            output=text if output is None else output,
            human_readable=text,
        )

    def _fail(self, arguments: Dict[str, Any], text: str) -> ToolResult:
        return ToolResult(
            tool_call_id=str(arguments.get("tool_call_id") or ""),
            tool_id=self.tool_id,
            status="error",
            success=False,
            error=text,
            human_readable=text,
        )

    @property
    def category(self) -> str:
        return "skills"

    @property
    def risk_level(self) -> str:
        return "low"


class SkillListTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_list"

    @property
    def name(self) -> str:
        return "skill_list"

    @property
    def display_phrase(self) -> str:
        return "skills listed"

    def plan_membership_default(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "List Agent Skills installed in Kerniq and SKILL.md skills already in the workspace. "
            "Each line has an id, whether it is on, and when to use it. "
            "This does not load the instructions. Call skill_load for that."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Optional words. Only skills whose id or description contain them are returned.",
                },
            },
            "required": [],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        opts = engine.current_options()
        workspace = engine.workspace_dir() if opts.get("include_project", True) else None
        records = engine.list_skills(engine.skills_root(), workspace=workspace)
        query = str(arguments.get("query") or "").strip().lower()
        if query:
            records = [
                record for record in records
                if query in str(record.get("id") or "").lower()
                or query in str(record.get("description") or "").lower()
            ]
        return self._done(arguments, engine.format_library(records), {"skills": [
            {"id": record["id"], "enabled": record["enabled"], "origin": record["origin"], "description": record["description"]}
            for record in records
        ]})


class SkillLoadTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_load"

    @property
    def name(self) -> str:
        return "skill_load"

    @property
    def display_phrase(self) -> str:
        return "skills loaded"

    def plan_membership_default(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "Load one Agent Skill by id. Returns the SKILL.md instructions and the files in that skill. "
            "Call this before following a skill. Do not invent the steps from the catalog line."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Skill id from the catalog or from skill_list."},
            },
            "required": ["id"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        opts = engine.current_options()
        workspace = engine.workspace_dir() if opts.get("include_project", True) else None
        result = engine.load_skill(
            str(arguments.get("id") or ""),
            workspace=workspace,
        )
        if not result.get("ok"):
            return self._fail(arguments, result.get("error") or "Skill not found.")
        return self._done(arguments, result.get("message") or "", result.get("skill"))


class SkillReadTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_read"

    @property
    def name(self) -> str:
        return "skill_read"

    @property
    def display_phrase(self) -> str:
        return "skill files read"

    def plan_membership_default(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "Read one file inside a skill, such as references/guide.md or scripts/extract.py. "
            "The path is relative to that skill folder. Use this when the loaded instructions name a file."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Skill id."},
                "path": {"type": "string", "description": "Relative path inside the skill. Example: references/forms.md"},
            },
            "required": ["id", "path"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        opts = engine.current_options()
        workspace = engine.workspace_dir() if opts.get("include_project", True) else None
        result = engine.read_skill_file(
            str(arguments.get("id") or ""),
            str(arguments.get("path") or ""),
            workspace=workspace,
        )
        if not result.get("ok"):
            return self._fail(arguments, result.get("error") or "Could not read that file.")
        return self._done(arguments, result.get("message") or "", {"path": result.get("path"), "truncated": result.get("truncated")})


class SkillSearchTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_search"

    @property
    def name(self) -> str:
        return "skill_search"

    @property
    def display_phrase(self) -> str:
        return "skill searches"

    def plan_membership_default(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "Search GitHub for repositories that may contain Agent Skills (SKILL.md). "
            "Does not install anything. Ask the user before calling skill_import."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Words, or owner/repo."},
                "limit": {"type": "integer", "description": "Maximum repositories (1-20).", "default": 8},
            },
            "required": ["query"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        found = engine.search_github(str(arguments.get("query") or ""), int(arguments.get("limit") or 8))
        text = engine.format_search(found)
        if not found.get("ok"):
            return self._fail(arguments, text)
        return self._done(arguments, text, found)


class SkillImportTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_import"

    @property
    def name(self) -> str:
        return "skill_import"

    @property
    def display_phrase(self) -> str:
        return "skills imported"

    @property
    def risk_level(self) -> str:
        return "medium"

    def plan_membership_default(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return (
            "Import Agent Skills into Kerniq. Source may be owner/repo, a GitHub URL "
            "(including a /tree/ or /blob/ path to one skill), a local folder, a zip, or SKILL.md text. "
            "A repository can hold many skills. Pass owner/repo/skills/name to import one. "
            "Do not import unless the user asked."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "GitHub URL, owner/repo, owner/repo/path, folder, zip, or SKILL.md text.",
                },
                "force": {
                    "type": "boolean",
                    "description": "Replace a skill that is already installed with the same id.",
                    "default": False,
                },
            },
            "required": ["source"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        opts = engine.current_options()
        result = engine.import_source(
            str(arguments.get("source") or ""),
            force=bool(arguments.get("force") or opts.get("replace_existing")),
            block_critical=bool(opts.get("block_critical")),
        )
        text = result.get("message") or result.get("error") or "Import failed."
        if not result.get("ok"):
            return self._fail(arguments, text)
        return self._done(arguments, text, {"installed": [item.get("id") for item in result.get("installed") or []]})


class SkillManageTool(_SkillTool):
    @property
    def tool_id(self) -> str:
        return "skill_manage"

    @property
    def name(self) -> str:
        return "skill_manage"

    @property
    def display_phrase(self) -> str:
        return "skill changes"

    @property
    def risk_level(self) -> str:
        return "medium"

    def plan_membership_default(self) -> bool:
        return False

    @property
    def description(self) -> str:
        return (
            "Enable, disable, or remove an installed skill. "
            "action is enable, disable, or remove. remove requires confirm true. "
            "A skill that only lives in the workspace is not deleted."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Skill id."},
                "action": {
                    "type": "string",
                    "description": "enable, disable, or remove.",
                    "enum": ["enable", "disable", "remove"],
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to remove.",
                    "default": False,
                },
            },
            "required": ["id", "action"],
        }

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        engine = _engine()
        action = str(arguments.get("action") or "").strip().lower()
        skill_id = str(arguments.get("id") or "")
        workspace = engine.workspace_dir()
        if action == "enable":
            result = engine.set_skill_enabled(skill_id, True, workspace=workspace)
        elif action == "disable":
            result = engine.set_skill_enabled(skill_id, False, workspace=workspace)
        elif action == "remove":
            result = engine.remove_skill(skill_id, confirm=bool(arguments.get("confirm")), workspace=workspace)
        else:
            return self._fail(arguments, "action must be enable, disable, or remove.")
        text = result.get("message") or result.get("error") or "Could not update that skill."
        if not result.get("ok"):
            return self._fail(arguments, text)
        return self._done(arguments, text, result)


def create_tools(plugin):
    return [
        SkillListTool(plugin),
        SkillLoadTool(plugin),
        SkillReadTool(plugin),
        SkillSearchTool(plugin),
        SkillImportTool(plugin),
        SkillManageTool(plugin),
    ]
