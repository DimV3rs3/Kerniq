"""Generate plugin and tool stubs for third-party development."""

from __future__ import annotations

from pathlib import Path


class PluginScaffoldGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def generate(self, plugin_id: str, name: str, description: str) -> Path:
        plugin_path = self.output_dir / plugin_id
        if plugin_path.exists():
            raise FileExistsError(f"Already exists: {plugin_path}")
        plugin_path.mkdir(parents=True)

        (plugin_path / "manifest.toml").write_text(
            f'''plugin_id = "{plugin_id}"
name = "{name}"
version = "0.1.0"
api_version = "1.0"
manifest_version = "1.0"
entry_point = "main.PluginImpl"
description = "{description}"
capabilities = ["tools"]
''',
            encoding="utf-8",
        )

        (plugin_path / "main.py").write_text(
            f'''"""Plugin: {name}"""

from __future__ import annotations

from typing import Any, Dict

from agent_platform.plugins.base import Plugin, PluginContext
from agent_platform.plugins.manifest import PluginManifest
from agent_platform.interfaces.tools import Tool, ToolResult
from agent_platform.interfaces.settings_schema import (
    SettingsSchema,
    SettingField,
    SettingType,
)


class ExampleTool(Tool):
    def __init__(self) -> None:
        self.cfg_prefix = "Hello"

    @property
    def tool_id(self) -> str:
        return "{plugin_id}_example"

    @property
    def name(self) -> str:
        return "example_tool"

    @property
    def description(self) -> str:
        return "Example tool from scaffold"

    @property
    def category(self) -> str:
        return "other"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{"text": {{"type": "string"}}}},
            "required": ["text"],
        }}

    def settings_schema(self):
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(
                    key="prefix",
                    label="Prefix",
                    type=SettingType.STRING,
                    default="Hello",
                ),
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if values and "prefix" in values:
            self.cfg_prefix = str(values["prefix"])

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        text = arguments.get("text", "")
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", "unknown"),
            tool_id=self.tool_id,
            status="success",
            output={{"text": f"{{self.cfg_prefix}}: {{text}}"}},
            human_readable=f"{{self.cfg_prefix}}: {{text}}",
        )


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="{plugin_id}",
            name="{name}",
            version="0.1.0",
            api_version="1.0",
            entry_point="main.PluginImpl",
            description="{description}",
            capabilities=["tools"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def settings_schema(self):
        return SettingsSchema(
            component_id="{plugin_id}",
            component_type="plugin",
            title="{name}",
            fields=[
                SettingField(
                    key="enabled_feature",
                    label="Enable feature",
                    type=SettingType.BOOL,
                    default=True,
                ),
            ],
        )

    async def initialize(self, context: PluginContext) -> bool:
        context.register_tool(ExampleTool())
        return True

    async def shutdown(self) -> None:
        pass
''',
            encoding="utf-8",
        )
        (plugin_path / "README.md").write_text(
            f"# {name}\n\nScaffold-generated plugin. Edit `main.py` and declare `settings_schema()` "
            "on tools/plugin for UI settings.\n",
            encoding="utf-8",
        )
        return plugin_path


class ToolScaffoldGenerator:
    """Write a single tool module stub under tools/."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def generate(self, tool_id: str, name: str, category: str = "other") -> Path:
        path = self.output_dir / f"{name}.py"
        if path.exists():
            raise FileExistsError(path)
        path.write_text(
            f'''"""Tool: {name}"""

from __future__ import annotations

from typing import Any, Dict

from agent_platform.interfaces.tools import Tool, ToolResult
from agent_platform.interfaces.settings_schema import SettingsSchema, SettingField, SettingType


class {name.title().replace("_", "")}Tool(Tool):
    def __init__(self) -> None:
        self.cfg_example = 1

    @property
    def tool_id(self) -> str:
        return "{tool_id}"

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def description(self) -> str:
        return "TODO: describe"

    @property
    def category(self) -> str:
        return "{category}"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {{"type": "object", "properties": {{}}, "required": []}}

    def settings_schema(self):
        return SettingsSchema(
            component_id=self.tool_id,
            component_type="tool",
            title=self.name,
            fields=[
                SettingField(key="example", label="Example int", type=SettingType.INT, default=1, minimum=0),
            ],
        )

    def apply_settings(self, values: Dict[str, Any]) -> None:
        if values and "example" in values:
            self.cfg_example = int(values["example"])

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", "unknown"),
            tool_id=self.tool_id,
            status="success",
            output={{}},
            human_readable="ok",
        )
''',
            encoding="utf-8",
        )
        return path
