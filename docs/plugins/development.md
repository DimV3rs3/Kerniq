# Writing a plugin

A plugin is one directory under `plugins/`. Another person can copy that folder in. Kerniq discovers it. Nothing in the core imports a plugin by name.

```
plugins/my_plugin/
  manifest.toml
  main.py
  tools/__init__.py
  README.md
```

`tools/` is optional. A tool pack under `src/Kerniq/tools/packs/<name>/` is the same idea for tools that ship with Kerniq: one folder, a manifest, the tools, and a README. Packs are discovered. Do not add a hardcoded import when you add a pack.

## Manifest

```toml
[plugin]
plugin_id = "my_plugin"
name = "My plugin"
version = "1.0.0"
api_version = "1.0"
entry_point = "main.PluginImpl"
description = "What this plugin does."

[capabilities]
tools = true

[tools]
expose_to_agent = false
```

`expose_to_agent` applies to every tool loaded from `tools/`. `false` is the default when the block is missing. Set it to `true` only when the model should be able to call those commands. A hidden tool is still registered, so the plugin can call it. It is omitted from the model prompt, the CLI tool list, and MCP.

## Plugin class

Subclass `Plugin` from `Kerniq.plugins.base`. `initialize` starts the plugin. It does not have to register tools. Folder tools are loaded after `initialize` returns true.

```python
from Kerniq.plugins.base import Plugin

class PluginImpl(Plugin):
    async def initialize(self, context):
        self._context = context
        return True

    async def shutdown(self):
        return None
```

## Tools that live in the folder

`plugins/my_plugin/tools/__init__.py` exports `create_tools(plugin)`.

```python
from Kerniq.interfaces.tools import Tool, ToolResult

class MyTool(Tool):
    def __init__(self, plugin):
        self._plugin = plugin

    @property
    def tool_id(self):
        return "my_tool"

    @property
    def name(self):
        return "my_tool"

    @property
    def description(self):
        return "Used by this plugin. Not an agent command unless the manifest exposes it."

    @property
    def input_schema(self):
        return {"type": "object", "properties": {}}

    async def execute(self, arguments, context):
        return ToolResult(success=True, output="ok")

def create_tools(plugin):
    return [MyTool(plugin)]
```

Do not call `context.register_tool` from `initialize` for these. The loader does it and applies `expose_to_agent`. `register_tool` still exists for a tool built at runtime. That path is private too, unless you pass `expose_to_agent=True` or set `_agent_visible = True` on the tool before registering it.

## Extending another plugin

A host lists slots. A guest offers a contribution. The contribution is attached only when the host id matches and the slot is one the host listed. Scanning does not call `initialize`.

```python
class PluginImpl(Plugin):
    def extension_slots(self):
        return ["settings", "panel"]

    def contributions(self):
        return [{
            "host": "plugin_web_ui",
            "slot": "settings",
            "id": "my_plugin",
            "label": "My plugin",
            "icon": "puzzle",
        }]
```

The Web UI ships the slots `settings` and `panel`. `catalog/Kerniq-llm-benchmark` is a separate plugin that fills both once it is installed. Its id is `llm-benchmark`. It is not part of the default kit. A host that returns no slots cannot be extended, even if a guest names it.

## Install

The default kit already contains the Web UI, Context Compact, and the Plugin Manager. Other plugins are installed.

`kerniq plugins check FOLDER` reports whether a folder is a complete standalone plugin. `kerniq plugins install owner/repo` downloads one. `kerniq plugins install --path FOLDER` installs a local folder. `kerniq plugins updates` compares installed add-ons with the source they were installed from. `kerniq plugins remove ID --yes` deletes an add-on. The Web UI, Context Compact, and the Plugin Manager cannot be removed.

Restart Kerniq after an install. `kerniq plugins list` shows what is loaded. `kerniq plugins validate` writes missing settings and rejects values the schema does not allow. Settings fields come from `settings_schema()` on the plugin class. See [settings.md](settings.md).
