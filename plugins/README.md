# Plugins

Kerniq loads every folder under `plugins/` that has a manifest. It does not import a plugin by name.

The default kit is the shell, the compactor, and the installer:

| Folder | Id | What it is |
|--------|-----|------------|
| `web_ui/` | `plugin_web_ui` | Browser UI. Host slots: `settings`, `panel`. |
| `context_compact/` | `plugin_context_compact` | Replaces older turns with a memory note when the window fills. |
| `plugin_manager/` | `plugin_plugin_manager` | Search, install, remove, and check updates for other plugins. |

Anything else is a separate plugin. The copies in `catalog/` are not loaded. Install one and Kerniq identifies it by the `plugin_id` in its manifest.

```bash
kerniq plugins check catalog/Kerniq-llm-benchmark
kerniq plugins install --path catalog/Kerniq-llm-benchmark
kerniq plugins install owner/repo
kerniq plugins updates
kerniq plugins remove llm-benchmark --yes
```

`catalog/Kerniq-office` and `catalog/Kerniq-model-advisor` install the same way. Their tools are offered to the model. The benchmark command is not.

A plugin's tools stay inside the plugin unless its manifest says:

```toml
[tools]
expose_to_agent = true
```

A plugin can add UI to another plugin only when that host returns the slot from `extension_slots()`. The guest lists the offer in `contributions()`.

```bash
kerniq plugins list
kerniq plugins ui
```

Server mode is a Web UI setting, not a separate plugin. `kerniq plugins ui -s server_mode true` turns it on. See the project README.
