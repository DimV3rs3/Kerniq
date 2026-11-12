# Plugins

Kerniq loads every folder under `plugins/` that has a manifest. It does not import a plugin by name.

The default kit is the shell, the compactor, the installer, and Skill Manager:

| Folder | Id | What it is |
|--------|-----|------------|
| `web_ui/` | `plugin_web_ui` | Browser UI. Host slots: `settings`, `panel`. |
| `context_compact/` | `plugin_context_compact` | Replaces older turns with a memory note when the window fills. |
| `plugin_manager/` | `plugin_plugin_manager` | Search, install, remove, and check updates for other plugins. |
| `skill_manager/` | `plugin_skill_manager` | Import Agent Skills (`SKILL.md`) from GitHub or a folder and offer them to the model. |

Anything else is a separate plugin. It is not part of this tree and it is not loaded from here. Install it into `plugins/` and restart, or use the Plugins tab.

```bash
kerniq plugins install owner/repo
kerniq plugins updates
kerniq plugins remove name --yes
```

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
