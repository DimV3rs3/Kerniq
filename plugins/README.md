# User / production plugins

Put installed plugins here (each folder with `manifest.toml` + `main.py`).

The Web UI plugin currently lives under `examples/plugins/web_ui_plugin` because it was developed as a reference implementation.
For a production layout you can copy or symlink it into this directory:

```
plugins/web_ui_plugin/  → copy from examples/plugins/web_ui_plugin
```

`examples/plugins/` is for demos and templates only (e.g. weather sample).
