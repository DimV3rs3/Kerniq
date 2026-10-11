# AI Agent Platform - Kerniq

Modular Open Source platform for autonomous AI agents.

**Default provider:** LM Studio (local). Falls back to Mock when offline (unless forced).

## Install / run

```bash
cd project
export PYTHONPATH=src
# or: pip install -e ".[dev]"

python -m Kerniq doctor
python -m Kerniq tools list
python -m Kerniq run --task "Say hello" --provider mock
python -m Kerniq plugins ui   # http://127.0.0.1:8765
```

## Tools

- Files: `read_file`, `write_file`, `create_file`, `edit_file`, `delete_file`, `list_directory` (recursive), `create_directory`, `file_exists`, `get_file_info`
- Terminal: `run_command`
- Web: `web_search`, `fetch_url`

Settings persist in `state/tool_settings.json`:

```bash
python -m Kerniq tools settings
python -m Kerniq tools set web_search_enabled true
```

## Config

`config/default.toml` — LM Studio URL, limits, UI port, `auto_install_deps`.

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -v
```

## Plugins

- `examples/plugins/weather_plugin`
- `examples/plugins/web_ui_plugin` — browser control panel
