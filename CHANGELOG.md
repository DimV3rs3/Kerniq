# Changelog

## 0.1.0 — Initial working release

- Package layout under `src/agent_platform`
- Contracts: models, tools, storage, providers, errors, approvals
- Agent + Orchestrator loop with tool calls and verification hook
- MockProvider (offline) and LM Studio OpenAI-compatible adapter
- Filesystem tools with workspace boundary enforcement
- Terminal tool with policy deny-list
- Security policy (risk levels, path validation)
- JSON session storage + SessionManager
- Plugin manager + example weather plugin
- MCP client/server adapters (optional `mcp` dependency)
- CLI: doctor, config, models, tools, plugins, sessions, run
- Offline unit/integration/security tests (11 passed)

## 0.1.1 — Tools, web search, UI, LM Studio default

- Expanded FS tools: create/edit/delete file, recursive list, get_file_info
- `web_search` (DuckDuckGo) + `fetch_url` via httpx (no urllib)
- Persistent tool settings (`state/tool_settings.json`) + CLI `tools set|settings`
- Auto dependency check/install on startup (`bootstrap.py`, `auto_install_deps`)
- LM Studio as default provider; doctor reports system + models + recommendations
- Browser UI plugin (`plugins ui` → http://127.0.0.1:8765)
