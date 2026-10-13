# MCP Server

Kerniq can act as an MCP **server** and expose selected internal tools to external MCP clients
(LM Studio chat, Claude Desktop, other agents, IDEs).

## Requirements

```bash
pip install -e ".[mcp]"
# or: pip install mcp
```

`kerniq` must be on `PATH` (or use the full path to `kerniq.exe` / `python -m Kerniq`).

## How it works

1. CLI starts `MCPServerAdapter` with the internal `ToolRegistry` (filesystem, web, terminal packs if enabled).
2. Only tools listed in `config/default.toml` → `[mcp].published_tools` are advertised (`list_tools`).
3. On `call_tool`, the adapter maps the MCP request to the internal `Tool.execute(...)` with a workspace-bound context.
4. Transport is **stdio** (official `mcp` ≥ 2.0 low-level `Server` + `stdio_server`). Logs go to **stderr**.

**Not every Kerniq tool is published by default.** Dangerous tools (`run_command`, write/delete file) stay off the allowlist unless you add them explicitly.

## Run

```bash
kerniq mcp validate
kerniq mcp serve
kerniq mcp serve --workspace E:\path\to\workspace
```

## Configuration

```toml
[mcp]
enabled = true
servers = []
published_tools = [
  "list_directory",
  "read_file",
  "file_exists",
  "get_file_info",
  "web_search",
  "fetch_url",
]
```

Match by **tool name** or **tool_id**.

## Connect to LM Studio (0.4.x) chat as an agent with tools

LM Studio is an **MCP client**: it spawns your server and lets a tool-capable model call tools during normal chat. You do **not** need to paste a system prompt every time once MCP is configured.

### 1. Install Kerniq with MCP

```bat
cd E:\Kerniq
pip install -e ".[dev,mcp]"
```

Ensure the console script is reachable, e.g.:

```bat
where kerniq
kerniq mcp validate
```

If `kerniq` is not on PATH, use the full path to `kerniq.exe` under  
`%APPDATA%\Python\Python3xx\Scripts\` or:

```bat
python -m Kerniq mcp serve --workspace E:\Kerniq\workspace
```

### 2. Edit LM Studio `mcp.json`

In LM Studio:

1. Right sidebar → **Program** tab  
2. **Install → Edit mcp.json**  
3. Add (adapt paths):

```json
{
  "mcpServers": {
    "kerniq": {
      "command": "kerniq",
      "args": [
        "mcp",
        "serve",
        "--workspace",
        "E:\\Kerniq\\workspace"
      ]
    }
  }
}
```

Windows alternatives if `kerniq` is not on PATH:

```json
"command": "python",
"args": ["-m", "Kerniq", "mcp", "serve", "--workspace", "E:\\Kerniq\\workspace"]
```

or absolute path to `kerniq.exe`.

File location: `%USERPROFILE%\.lmstudio\mcp.json` (also editable via the UI).

### 3. Enable MCP in LM Studio

- Use a **tool-capable** model (function/tool calling in the model card).
- In chat / server settings, allow **MCP / tools** and “Allow calling servers from mcp.json” if present.
- After saving `mcp.json`, LM Studio loads the server; tool list should include Kerniq tools (`web_search`, `fetch_url`, …).

### 4. Chat

Ask something that needs the web, e.g. “What is the latest release of X? Search and summarize.”  
The model should call `web_search` / `fetch_url` without you rewriting a custom agent prompt each time. LM Studio may show a confirmation UI for tool calls.

### Reality check

| Expectation | Reality |
|-------------|---------|
| Model uses `web_search` + `fetch_url` in LM Studio chat | **Yes**, if MCP is configured and the model supports tools |
| Full Kerniq Orchestrator loop inside LM Studio | **No** — LM Studio is the agent loop; Kerniq only **executes tools** |
| All Kerniq tools auto-exposed | **No** — only `published_tools` allowlist |
| Zero prompt engineering | Mostly — still depends on model quality and LM Studio tool UI |
| Multi-step autonomous coding agent | Prefer `kerniq run` / Web UI agent, not only MCP |

## Security

- Allowlist only.
- Same workspace path policy as the agent for filesystem tools.
- Prefer read-only + web tools for untrusted chat clients.
- stdio MCP is local-trust; no auth layer.

## Implementation notes

- Adapter: `Kerniq.mcp.server.MCPServerAdapter`
- Client adapter exists (`Kerniq.mcp.client`) for the reverse direction (Kerniq → external MCP servers); not required for LM Studio chat.
- Results returned as MCP `TextContent`
