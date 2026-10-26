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

Three files, shared by the console and the shell:

- `state/settings.json` — agent, API, prompt, chat
- `state/tools.json` — tool toggles and per-tool values
- `state/plugins.json` — per-plugin values

The first run writes defaults. A change from either side replaces those values in the same file. Validation adds a missing component with its schema defaults. A component that is no longer installed is removed from its file.

`kerniq plugins validate` and tool loading both run that reconciliation. Deleting a plugin also drops its block immediately.

## UI

Settings → Tools / Plugins:

- Left: grouped list (checkbox = enable; click **name** = detail panel)
- Right: fields from `settings_schema()`
- Save disabled until dirty; leaving Workspace warns if unsaved
- Reset selected / reset all

## CLI

The full command list, including `settings set`, `tools set`, and `plugins set`,
is in [docs/cli.md](../cli.md).

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
