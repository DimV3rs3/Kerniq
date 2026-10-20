# Web UI

Separate Kerniq plugin. It renders the runtime. It does not own agent settings.

Settings live in `state/settings.json` and are the same store the CLI reads with `kerniq settings show`. Stopping this plugin does not cancel a task that already started. The runtime keeps the session log and the UI only displays mode, plan, and tool order when it is open. Interface languages other than English are JSON packs imported from this plugin's settings.

Run: `kerniq plugins ui` (default `127.0.0.1:8765`).
