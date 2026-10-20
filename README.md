# Kerniq 0.1.5 — Modular Open Source AI Agent Platform

Local-first agent runtime with discovered tool packs, plugins, MCP, CLI, and
pluggable model providers (LM Studio, Ollama, DeepSeek, OpenRouter, OpenAI,
Claude API, Claude Code CLI, Gemini, Groq, Mistral, Mock).

## What this build actually does

Kerniq 0.1.5 runs a tool loop locally:

1. `kerniq run --provider mock` answers from `MockProvider` and can call the
   built-in file and shell tools. The reply is marked `outcome=unverified`
   unless you pass `--expect-file PATH` (or the caller sets file/syntax checks).
2. `kerniq run --provider lm_studio` uses LM Studio's OpenAI-compatible
   `POST /v1/chat/completions` for chat and tools. Model list/load/unload uses
   `GET/POST /api/v1/models`. If that server is down, the command exits with an
   error. It does **not** silently switch to mock.
3. `kerniq plugins ui` serves the existing Web UI (default `127.0.0.1:8765`)
   with chat, explorer, tool events, cancel, and an approval modal for
   high-risk tools.
4. Sessions from `kerniq run` are written under `sessions/` as JSON.

The shell is not an OS sandbox. See `docs/architecture/security.md`.
Context trimming keeps the system prompt, the original user goal, and the newest
complete tool-call groups. Token counts are an estimate (`len/4`) unless the
provider returns usage or a context length.

## Install

Ready-made scripts live in `scripts/`. Double-click or run one. They do not need Python on `PATH`.

| Platform | Command |
|----------|---------|
| Windows | `scripts\install.bat` |
| Linux, macOS | `bash scripts/install.sh` |

What the script does:

1. If `python`, `python3`, or `py -3.11` (or newer) is already on `PATH`, Kerniq is installed into that interpreter. No virtual environment is created.
2. If Python is not on `PATH`, the script looks for a local install and, if needed, downloads a private CPython into `.kerniq/runtime`. It then creates `.venv` and installs there. Launchers use that venv.
3. Install always goes through `python -m pip`, so a missing `pip` command does not matter.
4. Before installing, it records the packages already present. Uninstall removes only packages that were not there before. Packages you already had stay. A `.venv` is deleted only when this install created it. A downloaded private Python is deleted only when this install downloaded it.

When Python was already on `PATH`:

```bash
python -m Kerniq plugins ui
```

When it was not, and a venv was created:

```bash
.venv\Scripts\python.exe -m Kerniq plugins ui
.kerniq\kerniq.cmd plugins ui
```

```bash
.venv/bin/python -m Kerniq plugins ui
.kerniq/kerniq plugins ui
```

Uninstall (`scripts\uninstall.bat`, `bash scripts/uninstall.sh`) resets settings, `sessions/`, `logs/`, and `state/`, then removes only the packages this install added. Deleting the project files as well is a separate wipe (`uninstall.bat --wipe-project`).

The same scan runs when you install Kerniq, not when you save settings. Saving settings does not open consoles and does not download libraries. Shell commands inside the agent workspace use a private `.kerniq-venv` created in that workspace during install. If that venv is missing or its Python fails, Kerniq recreates it quietly. It is not the host Python and not a project `.venv`. Docker is not required. The UI launcher opens one console and closes it at once; the server itself has no window.

From the repository root you can also install by hand:

```bash
cd Kerniq
python -m pip install -e ".[dev,mcp]"
```

If your environment uses a private PyPI mirror that fails, force public index:

```bash
python -m pip install --index-url https://pypi.org/simple/ --break-system-packages -e ".[dev,mcp]"
```

After editable install:

```bash
kerniq --version
kerniq doctor
python -m Kerniq doctor   # equivalent
```

You do **not** need `export PYTHONPATH=src` when the package is installed this way.

### Optional extras

| Extra | Purpose |
|-------|---------|
| `dev` | pytest, ruff, mypy |
| `mcp` | official MCP SDK (`mcp` package) |

### Platforms and Python

Kerniq requires **Python 3.11 or newer** (`requires-python` in `pyproject.toml`).

| System | Support |
|--------|---------|
| Windows 10 and 11 | Yes |
| Windows 7 and 8 | No. CPython 3.11 does not support them. The last CPython for Windows 7 is 3.8, and this tree is not tested or packaged for 3.8. |
| Linux | Yes, on distributions that can install CPython 3.11 (glibc new enough for that build). |
| macOS | Yes, with Python 3.11+. |

Settings are three files, shared by the CLI and the Web UI. `state/settings.json` holds agent, API, prompt, and chat. `state/tools.json` holds tool toggles and per-tool values. `state/plugins.json` holds per-plugin values. The first run writes the defaults. A later change from either side replaces those values in the same file. `kerniq settings set api.max_tokens null` leaves a single reply uncapped. Tool and plugin values are added when those components are validated. A component that is no longer installed is removed on the next validation. Keys that only affect the shell are `chat.send_key`, `chat.file_ops_only`, `chat.aggregate_tools`, and `chat.show_reasoning_live`. The UI plugin is optional. Its own settings hold the interface language. Extra languages are JSON packs imported from the Web UI plugin page. A pack is checked before it is stored: a broken file is refused, and a partial pack reports which interface strings are still English.

### What changed in 0.1.5

- Context compaction keeps the last N messages and puts one compacted memory note above them. The note is preserved when the window is trimmed. The trigger is always a percent of the model window. The shrink target is a percent (strictly below the trigger) or a token count.
- Plan and Act each keep their own TODO. Items cannot be deleted, only marked done or skipped. With automatic handoff, Act starts from a cleared transcript plus the plan draft. The closed research list stays in the archive: Act does not redo it, and the UI keeps it visible. Without handoff, Plan answers the user directly.
- A refused approval is reported as `USER_DENIED` for those exact arguments. Repeating the same call does not prompt again.
- The footer uses red when the provider is unavailable, yellow when it is idle, orange while the model is working, and green when the selected model is loaded.
- Chat titles look for LM Studio and an embedding model even if another provider is selected. If LM Studio or that model is missing, the title is the first three words.
- Plan and Act can use different models. On a local provider the Plan model is unloaded and the Act model is loaded at handoff.

## Quick start

```bash
kerniq doctor
kerniq tools list
kerniq run --task "Say hello" --provider mock
kerniq plugins list
kerniq plugins ui          # http://127.0.0.1:8765 when web_ui plugin is present
```

### Web UI (desktop launcher)

```bash
kerniq plugins ui
# http://127.0.0.1:8765
```

No-console helpers (from repo root):

| Platform | Launcher |
|----------|----------|
| Windows | double-click `scripts/kerniq-ui.vbs` or `scripts/kerniq-ui.bat` |
| Linux/macOS | `bash scripts/kerniq-ui.sh` |

Console noise: **Plugins → Web UI → Console log level** (default: Warnings only).

Stop UI: settings bar **Stop UI**, or Ctrl+C in the terminal that started it.

**System tray:** full tray icon needs an extra native dependency (not bundled). Use the VBS/shell launchers to avoid a console window; the process may still appear briefly in the task list while the server runs.

### Uninstall

```bash
python -m Kerniq uninstall -y
python -m Kerniq uninstall -y --purge              # also sessions/logs/state
python -m Kerniq uninstall -y --wipe-project       # delete project source tree
```



### MCP server (stdio)

Expose allow-listed tools to any MCP client (Claude Desktop, other agents, etc.):

```bash
kerniq mcp validate
kerniq mcp serve
# or with explicit workspace:
kerniq mcp serve --workspace ./workspace
```

Published tools are controlled by `[mcp] published_tools` in `config/default.toml`.  
If the list is empty, read-only filesystem tools are published by default.

Example MCP client config (stdio):

```json
{
  "mcpServers": {
    "kerniq": {
      "command": "kerniq",
      "args": ["mcp", "serve", "--workspace", "/path/to/workspace"]
    }
  }
}
```

## Tools

- Files: `read_file`, `write_file`, `create_file`, `edit_file`, `delete_file`, `list_directory`, `create_directory`, `file_exists`, `get_file_info`, `search_code`
- Terminal: `run_command`
- Web: `web_search`, `fetch_url`

Tool toggles live in `state/tools.json`:

```bash
kerniq tools settings
kerniq tools set web_search_enabled true
kerniq settings show
```

## Plugin Manager plugin

Built-in plugin under `plugins/plugin_manager` provides tools:

| Tool | Role |
|------|------|
| `plugin_search` | Search GitHub for Kerniq-related plugins |
| `plugin_install` | Download zip of a GitHub repo into `./plugins/<name>` + security scan |
| `plugin_remove` | Delete an installed plugin folder (`confirm=true` required) |
| `plugin_security_scan` | Static heuristics (eval/exec/subprocess/pickle/…) |
| `plugin_list_installed` | List `./plugins/*` with manifest metadata |

Optional: set `GITHUB_TOKEN` / `GH_TOKEN` to raise GitHub API rate limits.

```bash
kerniq plugins list
```

## Update check

```bash
kerniq update
# private repo: export GITHUB_TOKEN=ghp_...
kerniq update --repo DimV3rs3/Kerniq
```

Release notes live on GitHub Releases (no CHANGELOG.md in the tree).

## License

MIT — see `LICENSE`.

## Config

`config/default.toml` — LM Studio URL, limits, UI port, MCP allowlist, `auto_install_deps`.

## Tests

```bash
pytest tests/ -v
# or still:
PYTHONPATH=src python -m pytest tests/ -v
```

## Documentation

- `docs/architecture/overview.md`
- `docs/mcp/server.md` / `docs/mcp/client.md`
- `docs/plugins/development.md`
