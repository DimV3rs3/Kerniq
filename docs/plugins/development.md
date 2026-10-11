# Plugin Development Guide

The AI Agent Platform allows you to extend its functionality by creating plugins. A plugin can provide new tools, background services, or custom logic.

## 1. Plugin Structure
A plugin is a directory containing at least two files:
- `manifest.toml`: Metadata and configuration.
- `main.py`: The implementation of the `Plugin` class.

### Example Directory Layout
```
plugins/my_custom_plugin/
├── manifest.toml
└── main.py
```

## 2. Creating a Manifest
The `manifest.toml` file tells the platform how to load your plugin.

```toml
[plugin]
plugin_id = "my_unique_id"
name = "My Custom Plugin"
version = "1.0.0"
api_version = "1.0"
entry_point = "main.PluginImpl"
description = "A brief description of what this plugin does."

[capabilities]
tools = true
```

## 3. Implementing the Plugin Class
Your plugin must implement the `Plugin` base class from `Kerniq.plugins.base`.

```python
from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.interfaces.tools import Tool, ToolResult

class MyTool(Tool):
    @property
    def tool_id(self) -> str: return "my_tool"
    # ... implement name, description, input_schema and execute() ...

class PluginImpl(Plugin):
    async def initialize(self, context: PluginContext):
        # Register tools to make them available to the agent
        context.register_tool(MyTool())
        return True

    async def shutdown(self):
        # Cleanup resources here
        pass
```

## 4. Deployment
To install your plugin, place the plugin directory into the `plugins/` folder of the platform installation. The `PluginManager` will automatically discover and load it on startup.
