from typing import Any, Dict, Optional
from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
from .engine import BenchmarkEngine

class BenchmarkProPlugin(Plugin):
    @property
    def manifest(self):
        import os
        # In a real scenario, we'd load this from the toml file in the plugin dir
        return None 

    def settings_schema(self) -> Optional[SettingsSchema]:
        return SettingsSchema(
            component_id="benchmark_pro",
            component_type="plugin",
            title="Professional LLM Benchmark",
            fields=[
                SettingField(
                    key="task",
                    label="Benchmark Task",
                    type=SettingType.TEXT,
                    default="Implement a simple calculator in Python with tests.",
                    description="The task the models will be evaluated on."
                ),
                SettingField(
                    key="results_path",
                    label="Results Directory",
                    type=SettingType.TEXT,
                    default=".workspace/benchmarks",
                    description="Where to save benchmark reports and workspaces."
                ),
                SettingField(
                    key="max_runtime_seconds",
                    label="Max Runtime per Model",
                    type=SettingType.INT,
                    default=3600,
                    description="Maximum time allowed for one model to work on the project."
                ),
                SettingField(
                    key="max_tool_calls",
                    label="Max Tool Calls",
                    type=SettingType.INT,
                    default=100,
                    description="Hard limit on the number of tool calls per model."
                ),
                SettingField(
                    key="show_progress",
                    label="Show Progress in UI/Console",
                    type=SettingType.BOOL,
                    default=True,
                    description="Whether to stream the benchmark progress to the output."
                ),
            ]
        )

    async def initialize(self, context: PluginContext) -> bool:
        # Initialize engine and register tools if needed
        self.engine = BenchmarkEngine(context, context.config.get("benchmark_pro", {}))
        return True

    async def shutdown(self) -> None:
        pass
