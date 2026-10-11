# Kerniq plugins

Real plugins live here (not examples):

| folder | id | role |
|--------|-----|------|
| `web_ui/` | plugin_web_ui | Cursor-like browser UI |
| `context_compact/` | context_compact | Context compaction |

```
plugins/<id>/
  manifest.toml
  main.py
  resources/
  static/          # optional (web_ui)
```

```bash
python -m Kerniq plugins ui
```

Enable **Server mode** in plugin settings to bind `0.0.0.0`, show LAN IP,
and disable OS folder dialog for remote browsers.
