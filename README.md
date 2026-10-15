# Kerniq 0.1.4 — Modular Open Source AI Agent Platform

Local-first agent runtime with discovered tool packs, plugins, MCP, CLI, and
pluggable model providers (LM Studio, Ollama, DeepSeek, OpenRouter, OpenAI,
Claude API, Claude Code CLI, Gemini, Groq, Mistral, Mock).

## What this build actually does

Kerniq 0.1.4 runs a tool loop locally:

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

Ready-made scripts live in `scripts/` and do the editable install for you:

| Platform | Command |
|----------|---------|
| Windows | `scripts\install.bat` |
| Linux, macOS | `bash scripts/install.sh` |

Uninstall without deleting the source tree resets settings, `sessions/`, `logs/`, and `state/` back to a fresh install. `scripts\uninstall.bat` and `bash scripts/uninstall.sh` do that. Deleting the project files as well is a separate, explicit wipe (`kerniq uninstall --wipe-project`) and is not what those scripts do.

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

The same settings file (`state/ui_settings.json`) is used by the CLI (`kerniq settings show`) and the Web UI. The UI does not own a private copy of agent settings. Stopping the UI does not stop a task that already started; the runtime keeps the session log.

### What changed in 0.1.4

- Context compaction keeps the last N messages and puts one compacted memory note above them. The note is preserved when the window is trimmed. The trigger is always a percent of the model window. The shrink target is a percent (strictly below the trigger) or a token count.
- Plan and Act each keep their own TODO. Items cannot be deleted, only marked done or skipped. With automatic handoff, Act starts from a cleared transcript plus the plan draft. Without handoff, Plan answers the user directly.
- A refused approval is reported as `USER_DENIED` for those exact arguments. Repeating the same call does not prompt again.
- The footer uses red (unavailable), yellow (idle), orange (the model is generating), and green (the task is still running and the model is waiting). Tokens per second are hidden when streaming is off.
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

Settings persist in `state/tool_settings.json`:

```bash
kerniq tools settings
kerniq tools set web_search_enabled true
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
