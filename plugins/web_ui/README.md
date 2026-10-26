# Web UI

Browser interface for Kerniq. It draws the chat, the editor, and settings. It does not own the agent. Agent, API, prompt, chat, and interface settings are the same `state/settings.json` the CLI reads with `kerniq settings show`. Stopping this plugin does not cancel a task that already started.

```bash
kerniq plugins ui
```

Default address: `http://127.0.0.1:8765`. `--host` and `--port` apply to this process only. `-s name value` saves a plugin setting before the server starts. Window launchers that hide the console are `scripts/kerniq-ui.vbs` (Windows) and `scripts/kerniq-ui.sh` (Linux and macOS).

On a desktop, switch between the agent chat and the editor from the header. On a phone held upright, only the agent chat is available. There is no header bar: the Kerniq mark and the new-chat button float over the chat. The mark opens the chat list over the chat. The chat does not change size: it shifts right and dims, and the list follows a finger. Settings open from the bottom of that list and slide in from the top. The back button, and a back swipe, return to that open list. Turn the phone sideways and the saved desktop layout comes back.

If the selected model, or the model that would be chosen automatically, reports that it can see images, photos can be attached. Otherwise the attach menu does not offer them.

This plugin is a host. `extension_slots()` returns `settings` and `panel`. Another plugin can add a settings section or a window only by contributing to one of those slots. The benchmark plugin does both.

Interface languages other than English are JSON packs imported from Interface settings. Server mode (one process, one workspace per browser user) is a setting of this plugin. It is documented in the project README.
