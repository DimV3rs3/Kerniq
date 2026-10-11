# Component settings (tools & plugins)

## Model

Each tool/plugin may implement:

```python
def settings_schema(self) -> SettingsSchema | None: ...
def apply_settings(self, values: dict) -> None: ...
@property
def category(self) -> str:  # tools only
```

`SettingsSchema` / `SettingField` live in `Kerniq.interfaces.settings_schema`.

## Storage

Per-component JSON files (not one giant config):

- `state/tools/<tool_id>.json`
- `state/plugins/<plugin_id>.json`

Loaded via `ComponentSettingsStore`.

## UI

Settings → Tools / Plugins:

- Left: grouped list (checkbox = enable; click **name** = detail panel)
- Right: fields from `settings_schema()`
- Save disabled until dirty; leaving Workspace warns if unsaved
- Reset selected / reset all

## CLI

```bash
python -m Kerniq settings show
python -m Kerniq settings reset
```

## Scaffold

```python
from pathlib import Path
from Kerniq.devtools.plugin_scaffold import PluginScaffoldGenerator, ToolScaffoldGenerator
PluginScaffoldGenerator(Path("examples/plugins")).generate("my_plugin", "My Plugin", "desc")
ToolScaffoldGenerator(Path("src/Kerniq/tools")).generate("my_tool_id", "my_tool", "other")
```
