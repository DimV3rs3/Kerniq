# Command reference

The console entry point is `kerniq`. After an editable install the same
commands are `python -m Kerniq ...`. Run `kerniq` or `kerniq --help` to print
the command list. `kerniq --version` prints the version and exits.

Commands below are the ones the CLI actually accepts. Values that belong to a
plugin or a tool are checked against that component's schema before they are
written. A rejected value is not saved.

## Common environment

| Variable | Effect |
|----------|--------|
| `KERNIQ_SERVER` | Remote Web UI address, same as `run --server`. |
| `KERNIQ_API_KEY` | API key for that remote address, same as `run --api-key`. |
| `KERNIQ_ROOT` | Project folder, used when plugin discovery cannot find `plugins/`. |
| `KERNIQ_NO_AUTO_UPDATE` | `1`, `true`, or `yes` skips the release check that runs before most commands. |
| `GITHUB_TOKEN` or `GH_TOKEN` | Raises the GitHub rate limit for `kerniq update` and for plugin search. |

`uninstall`, `remove`, `update`, `server`, `--help`, and `--version` never
auto-update. Other commands may apply a newer GitHub release and re-run
themselves. Settings and `state/` are kept.

---

## `kerniq doctor`

Checks the configuration, installed extras, and whether LM Studio answers.
Exit code `0` means the report is clean. Exit code `1` means something in the
report failed.

`kerniq models check` runs the same check.

## `kerniq config validate`

Loads `config/default.toml` (and any overlay the settings loader applies) and
prints the default provider, the workspace, and `auto_install_deps`. Any other
`config` action prints the usage line and exits `1`.

## `kerniq run`

Run one task in the saved workspace.

```bash
kerniq run --task "Say hello" --provider mock
kerniq run --task "Read the project" --workspace ./workspace --provider lm_studio
kerniq run --server http://HOST:8765 --api-key KEY --task "Read the project"
```

| Flag | Meaning |
|------|---------|
| `--task TEXT` | Required. The user goal. |
| `--workspace PATH` | Workspace for this task. Default is `agent.workspace` in `state/settings.json`, then `workspace_root` in `config/default.toml`. |
| `--provider ID` | Provider id from `kerniq models list`. Omit it to use the saved provider. |
| `--server URL` | Talk to a Kerniq that is already running, for example `http://10.0.0.8:8765`. Required on another computer. |
| `--api-key KEY` | API key for `--server`. The key does not replace the address. |

Remote mode needs both the address and the key. A missing address or a
missing key exits `2` and does not start a local agent. `401` from the server
means the key was rejected.

On the local path, a named `--provider` that cannot be reached exits `1`.
See the provider note in the README for the single LM Studio fallback.

## `kerniq models`

```bash
kerniq models list
kerniq models check
kerniq models loaded
kerniq models load --model MODEL [--alongside | --unload]
kerniq models unload-all
```

| Action | Meaning |
|--------|---------|
| `list` | Prints every provider id. Then lists LM Studio models if that server answers, or prints `LM Studio: unreachable`. |
| `check` | Same as `kerniq doctor`. |
| `loaded` | Models currently loaded in LM Studio. |
| `load` | Loads `--model`, or the model saved in settings. If another model is already loaded and you pass neither `--alongside` nor `--unload`, an interactive terminal asks what to do. A non-interactive shell exits `2` and does not guess. |
| `unload-all` | Unloads every loaded LM Studio instance. |

`--alongside` loads next to models already in memory. `--unload` unloads idle
models that are not the one you asked for, then loads it.

## `kerniq tools`

```bash
kerniq tools list
kerniq tools settings
kerniq tools set web_search_enabled true
```

`list` prints each discovered tool and the short phrase the UI shows.

`settings` prints the saved tool block and the path of `state/tools.json`.

`set KEY VALUE` writes one field. `true`/`false`/`yes`/`no` become booleans.
A whole number becomes an int, a decimal becomes a float, anything else stays
a string.

Toggles that exist out of the box:

| Key | Default |
|-----|---------|
| `fs_enabled` | true |
| `terminal_enabled` | true |
| `web_search_enabled` | true |
| `fetch_url_enabled` | true |
| `max_tool_output_chars` | 50000 |
| `fs_max_read_bytes` | 200000 |
| `fs_list_max_entries` | 500 |
| `fs_list_max_depth` | 5 |
| `terminal_default_timeout` | 30 |
| `terminal_max_output_chars` | 50000 |
| `web_search_max_results` | 5 |
| `web_search_timeout` | 20 |
| `fetch_url_timeout` | 20 |
| `fetch_url_max_bytes` | 100000 |

Built-in tool names include `read_file`, `write_file`, `create_file`,
`edit_file`, `delete_file`, `list_directory`, `create_directory`,
`file_exists`, `get_file_info`, `search_code`, `run_command`, `web_search`,
and `fetch_url`. Packs can add more. `kerniq tools list` is the live list.

## `kerniq plugins`

```bash
kerniq plugins list
kerniq plugins validate
kerniq plugins set plugin_web_ui -s port 9000
kerniq plugins set plugin_web_ui -s host 0.0.0.0 -s server_mode true
kerniq plugins ui
kerniq plugins ui --host 127.0.0.1 --port 8765
```

| Action | Meaning |
|--------|---------|
| `list` | Plugins discovered under `plugins/`. A plugin with **Show in plugin list** off is omitted. Prints `on` or `off`, and an error if loading failed. |
| `validate` | Writes missing plugin defaults and replaces values the schema rejects. Then loads every plugin. Exit `1` if a plugin failed to load. |
| `set PLUGIN_ID -s NAME VALUE` | Saves one or more settings for that plugin. Repeat `-s`. An invalid value is refused and nothing from that call is applied. |
| `ui` | Starts the Web UI and blocks until Ctrl+C. |

`plugins ui` flags:

| Flag | Meaning |
|------|---------|
| `--host HOST` | Bind address for this process only. Does not rewrite the saved setting. |
| `--port PORT` | Port for this process only. |
| `-s NAME VALUE` | Save a Web UI setting before the server starts. Same checks as `plugins set`. |

Web UI settings (`plugin_web_ui`):

| Key | Default | Meaning |
|-----|---------|---------|
| `host` | `127.0.0.1` | `127.0.0.1` is this computer only. `0.0.0.0` is every interface. Applied on the next start. |
| `port` | `8765` | TCP port, 1–65535. |
| `server_mode` | false | One Kerniq for every client. Forces `0.0.0.0` after a restart. |
| `lan_access` | false | Also binds `0.0.0.0`. Server mode already does this. |
| `show_footer` | true | Bottom status bar. |
| `ui_locale` | `en` | Interface language. English is built in. Other languages are imported packs. |
| `log_level` | `warning` | `debug`, `info`, `warning`, `error`, or `critical`. |

If the Web UI plugin is not found, the command prints the directories it
searched and tells you to set `KERNIQ_ROOT`.

## `kerniq sessions`

```bash
kerniq sessions list
kerniq sessions show SESSION_ID
```

`list` prints id, goal, and status for sessions under `sessions/`.
`show` prints one session. The id is the UUID stored with that session.
A missing id exits `1`.

## `kerniq server`

Server-mode address, storage, and the API key. Run these on the machine that
hosts Kerniq, not in a browser on another PC.

```bash
kerniq server show
kerniq server key
kerniq server key --rotate
kerniq server init
kerniq server db --host 127.0.0.1 --port 3306 --user USER --password PASS --name kerniq
kerniq server set users-root /var/lib/kerniq/homes
kerniq server set quota-gb 8
kerniq server set model-url http://127.0.0.1:1234
```

| Action | Meaning |
|--------|---------|
| `show` | Bind address, whether an API key exists, user-folder root, quota, model URL, and `mysql` or `json` storage. Does not print the key. |
| `key` | Prints the API key a remote console must send. Creates one if it is missing. |
| `key --rotate` | Replaces the key and prints the new one. Old consoles stop working. |
| `init` | Asks which database to use and creates it. Kerniq creates the database. |
| `db` | Creates a MySQL database from the flags and saves its URL. The password is not printed. Restart the Web UI so chats use it. |
| `set users-root PATH` | Where new user folders are created. Refuses the disk root and system directories. Existing folders stay where they are. Restart to pick this up. |
| `set quota-gb N` | Per-user disk limit, from 1 to 10240. No restart required. |
| `set model-url URL` | LM Studio or Ollama on the server machine. Must start with `http://` or `https://`. |

## `kerniq settings`

Shared settings in `state/settings.json`, plus a look at the tool and plugin
files.

```bash
kerniq settings show
kerniq settings set agent.max_iterations 20
kerniq settings set api.max_tokens null
kerniq settings reset
kerniq settings languages
kerniq settings language
kerniq settings language Russian
```

| Action | Meaning |
|--------|---------|
| `show` | Prints every saved section. A stored API token is shown as `***`. |
| `set SECTION.NAME VALUE` | Writes one field. `true`/`false`, integers, and floats are parsed. `null` or `none` clears an optional number such as `api.max_tokens`. An unknown section or a value the schema rejects is not saved. |
| `reset` | Clears tool and plugin blocks. Main settings stay. Defaults are written again the next time those components are validated. |
| `languages` | Lists response-language codes and English names. |
| `language` | Prints the current response language. |
| `language VALUE` | Sets it. Accepts a code (`ru`) or an English name (`Russian`). |

Sections in `settings.json`:

| Section | What it controls |
|---------|------------------|
| `agent` | `max_iterations`, `max_tokens`, `temperature`, `top_p`, `timeout_seconds`, `workspace`, `undo_history_size`, `loop_retries` |
| `api` | `provider`, `base_url`, `model`, `split_models`, `act_model`, `api_token`, `binary_path`, `temperature`, `max_tokens`, `auto_model_load`, `model_load_action` |
| `prompt` | `system_prompt`, `include_tool_catalog` |
| `chat` | Streaming, reasoning, send key, file-op display, tool aggregation, `response_language`, `auto_approve_up_to`, Plan/Act (`agent_mode`, `auto_act_after_plan`, `mode_auto`, `compose_plan`), external attachments |
| `interface` | Layout, motion, highlight, thinking, notifications |

`chat.auto_approve_up_to` is `read_only`, `low`, `medium`, `high`, or `all`.
`all` skips the human prompt. Critical actions still need a real approval
channel; headless mode denies them when nobody can answer.

Keys that only affect the shell are `chat.send_key` (`enter` or
`shift_enter`), `chat.file_ops_only`, `chat.aggregate_tools`, and
`chat.show_reasoning_live`.

## `kerniq mcp`

```bash
kerniq mcp validate
kerniq mcp serve
kerniq mcp serve --workspace ./workspace
kerniq mcp install
```

| Action | Meaning |
|--------|---------|
| `validate` | Prints whether MCP is enabled, whether the SDK is installed, the published-tool setting, and how many client servers are configured. Exit `1` if the SDK is missing. |
| `serve` | MCP server on stdio. Blocks. `--workspace` is the root tools may touch. Default is the configured workspace. |
| `install` | Writes a portable MCP client config for this machine, and updates LM Studio if it is installed. |

Published tools come from `[mcp] published_tools` in `config/default.toml`.

- An empty list publishes every discovered tool the security policy would run
  without a human. Plugin tools and `update_plan` are never published.
- `["*"]` publishes every non-critical tool, still excluding plugin tools.
- An explicit list is a manual allow-list. Names are still checked by the
  policy, and plugin tools are still dropped.

Install the SDK with `python -m pip install -e ".[mcp]"` or `pip install mcp`.
INFO logs from `mcp serve` go to `state/mcp.log`, not to stderr, so an MCP
client does not treat them as errors.

## `kerniq update`

```bash
kerniq update
kerniq update --repo owner/name
```

Compares this install with the latest GitHub release of `DimV3rs3/Kerniq`
(or `--repo`). Prints the release page when a newer version exists.

| Exit | Meaning |
|------|---------|
| `0` | Up to date, or no remote version. |
| `2` | A newer release exists. The command does not install it. |
| `1` | GitHub refused the request (authentication). |

A private repository needs `GITHUB_TOKEN`.

## `kerniq uninstall`

Also available as `kerniq remove`.

```bash
kerniq uninstall -y
kerniq uninstall -y --purge
kerniq uninstall -y --wipe-project
```

| Flag | Meaning |
|------|---------|
| `-y`, `--yes` | Do not ask for confirmation. |
| `--purge` | Also delete `sessions/`, `logs/`, `state/`, and `__pycache__` under the project root. |
| `--wipe-project` | Also delete the Kerniq source tree from disk. This is permanent. |

Uninstall removes the console script and only the packages this install
added. Packages that were already present stay. Without `-y` the command
asks before it deletes anything.
