# Kerniq 0.1.8

Kerniq is a local-first platform for AI agents. One process takes a task, asks a model, runs the tools that model requests, and keeps the session. The same loop is used by the command line, the Web UI, and the MCP server. A model provider or a plugin is an adapter. It is not a second copy of the loop.

File tools may touch only the workspace you set. The model is shown `./workspace` and `./attachments`, never the real directory, on Linux, Windows, and macOS, including when server mode is off. `run_command` is not an operating-system sandbox: by default it cannot use sudo, inspect the host, or leave those folders. A desktop agent setting, off by default, can allow real paths and privileged commands after a 5-second confirmation. Server mode does not offer that setting. It still refuses disk wipes, formatting, and shutdown. Approvals and limits are described in [docs/architecture/security.md](docs/architecture/security.md).

## What it does

- Runs a task against a local or hosted model. Built-in providers include LM Studio, Ollama, OpenAI, Anthropic, Gemini, Groq, Mistral, DeepSeek, OpenRouter, and the Claude Code CLI. `mock` is the offline provider used by tests and by `kerniq run --provider mock`.
- Shares one settings store between the CLI and the Web UI: agent, API, prompt, chat, and interface in `state/settings.json`, tool values in `state/tools.json`, plugin values in `state/plugins.json`.
- Ships tool packs for files, the workspace shell, the web, and the plan. The live list is `kerniq tools list`. A picture is sent only when the provider catalog says that model can see images. The model looks at a file with `view_image`, not by reading the bytes as text.
- Keeps Plan mode and Act mode separate. Each mode has its own plan.
- Loads plugins from folders under `plugins/`. The default kit is the Web UI, Context Compact, and the Plugin Manager. Every other plugin is a separate folder Kerniq identifies by its manifest after it is installed. `catalog/` holds those plugins so they can be published on their own. They are not loaded until then. A plugin's own tools stay out of the agent's command list unless that plugin's manifest says so. A plugin can add a screen to another plugin only when the host declares a slot for it.
- Includes server mode. One Kerniq process serves every browser. Each browser is a separate user with its own chats and its own workspace. MySQL is optional.
- On a phone held upright, the Web UI stays in the agent chat. Landscape and desktop keep the editor layout.

## Install and launch

Kerniq needs Python 3.11 or newer. Windows 10 and 11, current Linux, and macOS are supported. Windows 7 and 8 are not.

The installers and the window launchers are in `scripts/`. They do not need Python already on `PATH`.

| File | Use |
|------|-----|
| `scripts/install.bat`, `scripts/install.ps1` | Install on Windows |
| `scripts/install.sh` | Install on Linux and macOS. `bash scripts/install.sh --server` is the only install that then asks for a database. |
| `scripts/kerniq-ui.bat`, `scripts/kerniq-ui.vbs` | Start the Web UI on Windows without a console (`kerniq-ui.vbs`) or with one (`kerniq-ui.bat`) |
| `scripts/kerniq-ui.sh` | Start the Web UI on Linux and macOS |
| `scripts/uninstall.bat`, `scripts/uninstall.ps1`, `scripts/uninstall.sh` | Remove the install. See Uninstall below. |

```bat
scripts\install.bat
```

```bash
bash scripts/install.sh
```

What the installer does:

1. If `python`, `python3`, or `py -3.11` (or newer) is already on `PATH`, Kerniq is installed into that interpreter. No virtual environment is created.
2. If Python is not on `PATH`, the script looks for a local install and, if needed, downloads a private CPython into `.kerniq/runtime`. It then creates `.venv` and installs there. The launchers use that environment.
3. Install always goes through `python -m pip`. A missing `pip` command does not matter.
4. Before installing, it records the packages already present. Uninstall removes only packages that were not there before. A `.venv` is deleted only when this install created it. A downloaded private Python is deleted only when this install downloaded it.

From the repository root you can also install by hand:

```bash
python -m pip install -e ".[dev,mcp]"
```

Optional extras: `dev` (pytest, ruff, mypy), `mcp` (the MCP SDK), `mysql` (PyMySQL, only for server mode with MySQL).

Start the Web UI after install:

```bash
kerniq plugins ui
```

The default address is `http://127.0.0.1:8765`. If Python was not on `PATH` and the installer created an environment, use the launcher instead:

```bat
.kerniq\kerniq.cmd plugins ui
scripts\kerniq-ui.vbs
```

```bash
.kerniq/kerniq plugins ui
bash scripts/kerniq-ui.sh
```

Stop the UI from the status bar, or with Ctrl+C in the terminal that started it. Console noise is **Plugins → Web UI → Console log level** (default: warnings only). A saved host of `0.0.0.0`, LAN access, or server mode listens on every interface. The console prints the address. A host change applies on the next start.

## Commands

`kerniq` and `python -m Kerniq` are the same program after install. `kerniq --help` prints the command list. `kerniq --version` prints `0.1.8`. Every flag is in [docs/cli.md](docs/cli.md).

| Command | What it does |
|---------|----------------|
| `kerniq doctor` | Checks the configuration, extras, and whether LM Studio answers. |
| `kerniq run --task "Say hello" --provider mock` | Runs one task. `--workspace` overrides the saved workspace. `--provider` overrides the saved provider. A named provider that is down exits with an error. It does not switch to another provider. The only fallback is the default path: saved provider is LM Studio, you did not pass `--provider`, and LM Studio is unreachable. The CLI then uses mock and says so. |
| `kerniq models list` | Prints provider ids, then LM Studio models if that server answers. Also `loaded`, `load`, `unload-all`. |
| `kerniq tools list` | Tools the agent can see, and the short phrase the UI shows. `tools settings` and `tools set KEY VALUE` read and write `state/tools.json`. |
| `kerniq plugins list` | Plugins found under `plugins/`. `plugins validate` writes missing defaults and refuses values the schema rejects. `plugins set ID -s name value` saves one plugin setting. |
| `kerniq plugins ui` | Starts the Web UI and blocks until Ctrl+C. `--host` and `--port` apply to this process only. `-s name value` saves a Web UI setting before the server starts. `kerniq autostart on` starts that same UI in the background at the next sign-in. |
| `kerniq settings show` | Prints the shared settings. `settings set api.max_tokens null` leaves one reply uncapped. |
| `kerniq sessions list` | Sessions written by `kerniq run` under `sessions/`. `sessions show ID` prints one. |
| `kerniq server show` | Server-mode bind address, storage, and whether an API key exists. `server key` prints the key a remote console must send. `server init` creates the optional database. Kerniq creates the database. You do not create it first. |
| `kerniq mcp serve` | Exposes an allow-list of tools over stdio. See [docs/mcp/server.md](docs/mcp/server.md). |
| `pytest tests/ -v` | The standard suite. It does not need an API key, a network, or LM Studio. |

A remote console talks to a Kerniq that is already running. It needs both the address and the key. The key does not find the server.

```bash
kerniq run --server http://HOST:8765 --api-key KEY --task "Read the project"
```

`KERNIQ_SERVER` and `KERNIQ_API_KEY` are the same two values. `KERNIQ_ROOT` is the project folder when plugin discovery cannot find `plugins/`.

## Using Kerniq

1. Install, then start `kerniq plugins ui` or run `kerniq run --task "..."`.
2. Choose a provider in **API & model**, or pass `--provider`. LM Studio chat is `POST /v1/chat/completions`. Load and unload use `/api/v1/models`. Hosted providers need their own key.
3. Set the workspace. That directory is the only place file tools may read and write. In the Web UI, type a path or use Browse. Browse is hidden in server mode, because the browser is not on the server's disk.
4. Send a task. Kerniq checks the tool arguments, the workspace boundary, and the approval policy, then runs the tool and sends the result back. The loop stops when the task is done, when you cancel it, or when a limit is hit (iterations, tool calls, or time).
5. `kerniq run` stores that session under `sessions/` as JSON. The Web UI stores chats for the current user.

Platform defaults that are not per-user (LM Studio URL, limits, the MCP allow-list, `auto_install_deps`) live in `config/default.toml`. The first run writes the user defaults. A later change from the CLI or the Web UI replaces those values in the same file. `kerniq plugins validate` writes missing component defaults and drops a component that is no longer installed.

Context trimming keeps the system prompt, the original user goal, and the newest complete tool-call groups. Token counts are an estimate (`len/4`) unless the provider returns usage or a context length. Context Compact ships in the default kit. It can replace older turns with a memory note when the transcript crosses a percent of the model window. Its settings are in that plugin's folder. Turn it off there if you only want the trim.

### System readings

Kerniq reads this computer's operating system, CPU, memory, and, when `nvidia-smi` is present, GPU memory. Those readings stay on this computer. They are not sent to a model provider, to GitHub, or to any other host. Kerniq uses them locally, and a plugin may use the same local readings. The model advisor does that when it compares a model's quantization, parameter count, and context window with this machine. It does not upload the readings either.

### Plugins

A plugin is one folder. Kerniq discovers `plugins/<name>/manifest.toml` and `main.py`. It does not import plugins by name. Tools that belong to the plugin go in `plugins/<name>/tools/` and load with the plugin. They stay inside the plugin. They are not added to the agent's command list unless that plugin's `manifest.toml` contains:

```toml
[tools]
expose_to_agent = true
```

The default is hidden. Hidden tools are also left out of `kerniq tools list`, the system prompt, and MCP.

A plugin may attach to another plugin only where the host allows it. The host returns slot names from `extension_slots()`. The other plugin offers `{host, slot, id, label, icon}` from `contributions()`. An offer is kept only when the host lists that slot. The Web UI offers `settings` and `panel`. The LLM benchmark plugin fills both after it is installed: a Benchmark item in settings, and a separate window with the run state. It is not part of the kit. Its id is `llm-benchmark`. Copy a plugin folder into `plugins/` and restart, or install it from the Plugins tab. Details: [docs/plugins/development.md](docs/plugins/development.md).

`create_file`, `write_file`, `edit_file`, and `read_file` refuse `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.odt`, `.ods`, and `.odp`. Those are Office documents. The Office plugin (`catalog/Kerniq-office`) creates and edits them, including numbered tables, styles, and fonts, for Microsoft Office and LibreOffice.

### Server mode

Server mode is part of Kerniq, not a plugin. Turn it on in the Web UI, or before start:

```bash
kerniq plugins ui -s host 0.0.0.0 -s server_mode true
kerniq server key
```

- The site sets a cookie that is only a user id. A browser without a cookie becomes a new user.
- Chat, model, and interface settings stay in that browser. The API key is encrypted in the browser. The server does not store it and does not send a saved key back.
- Each user gets a private folder under the admin root: `workspace/` and `attachments/`. The model is shown `./workspace` and `./attachments`, never the cookie id and never a disk path. The browser still addresses that folder as `/workspace`.
- Right-click download (a file, a folder as a zip, or the open directory when the click is on empty space) exists only in server mode. "Show in explorer" and Browse are not shown there.
- MySQL is optional. Without it, chats stay in JSON and Kerniq says so on every start. `kerniq server init` creates the database when you want one.
- When the site listens on `0.0.0.0`, Kerniq prints every LAN address. `127.0.0.1` is the server itself. Private addresses work only on the same network. If the page does not load, allow that TCP port in the host firewall and in the cloud security group.
- Models are not unloaded while a task is running. The next task waits.
- An administrator can move the directory that holds user homes onto another disk, and can set a per-user disk quota. Kerniq tells the model when that user's disk is nearly full.

```bash
kerniq server show
kerniq server set users-root /mnt/disk/kerniq-users
kerniq server set quota-gb 8
```

### Web UI on a phone

Portrait (the screen is taller than it is wide, and no wider than 820px) is the agent chat only. The round Kerniq mark opens the chat list. The list slides over the chat: the chat keeps its size, moves 30% to the right, and dims. The list covers about 30% of that chat. A pencil button starts a new chat. The bottom bar is attach, the message field, and send. The bar is about 88% of the width until the field is focused, then it uses the full width. Settings open from the chat list and slide down from the top. The section list is icons. Two-column settings become one column. Save floats at the lower left, with Cancel beside it. Turn the phone sideways, or use a wider window, and the desktop editor layout returns, including the layout you last saved.

## Uninstall

```bat
scripts\uninstall.bat
```

```bash
bash scripts/uninstall.sh
```

Uninstall resets settings, `sessions/`, `logs/`, and `state/`, then removes only the packages this install added. Deleting the project files as well is a separate wipe: `uninstall.bat --wipe-project` (the shell script accepts the same flag). A `.venv` or a private Python runtime is removed only if this install created it.

## Documentation

- [docs/cli.md](docs/cli.md) — every command and flag
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — what changed in 0.1.8
- [docs/architecture/overview.md](docs/architecture/overview.md) — how the pieces fit
- [docs/architecture/security.md](docs/architecture/security.md) — workspace and approvals
- [docs/plugins/development.md](docs/plugins/development.md) — writing a plugin
- [docs/plugins/settings.md](docs/plugins/settings.md) — tool and plugin settings
- [docs/mcp/server.md](docs/mcp/server.md) — exposing tools to other clients

## License

MIT. See [LICENSE](LICENSE).
