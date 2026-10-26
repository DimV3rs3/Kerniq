# Plugins

Each plugin is one folder under `plugins/`. Kerniq discovers the folder. The core does not import a plugin by name. Copy a folder in and restart.

```
plugins/<name>/
  manifest.toml
  main.py
  tools/__init__.py    # optional; create_tools(plugin) -> list of tools
  README.md
  resources/           # optional
  static/              # optional
```

Tools in `tools/` load with the plugin. They are not agent commands unless `manifest.toml` says so:

```toml
[tools]
expose_to_agent = true
```

Leave the flag out, or set it to `false`, and the tool stays inside the plugin. It does not appear in the model prompt, `kerniq tools list`, or MCP.

A plugin can add UI to another plugin only when that host returns the slot from `extension_slots()`. The guest lists the offer in `contributions()`. Offers for a slot the host did not declare are ignored.

| Folder | Id | What it is |
|--------|-----|------------|
| `web_ui/` | `plugin_web_ui` | Browser UI. Host slots: `settings`, `panel`. |
| `benchmark_pro/` | `benchmark_pro` | Runs the selected provider's models. Private tool. Adds a Benchmark section and window to the Web UI. |
| `context_compact/` | `plugin_context_compact` | Replaces older turns with a memory note when the transcript gets large. |
| `plugin_manager/` | `plugin_plugin_manager` | Lists, validates, and scaffolds other plugins and tool packs. |

```bash
kerniq plugins list
kerniq plugins ui
```

Server mode is a Web UI setting, not a separate plugin. `kerniq plugins ui -s server_mode true` turns it on. See the project README.
