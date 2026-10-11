# MCP Client Integration

The AI Agent Platform can act as an MCP (Model Context Protocol) client, allowing it to use tools provided by external MCP servers.

## Configuration
External MCP servers are configured in `config/default.toml` under the `[mcp]` section:

```toml
[mcp]
enabled = true
servers = [
    { name = "filesystem", command = "npx", args = ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"] },
    { name = "github", command = "npx", args = ["-y", "@modelcontextprotocol/server-github"], env = { GITHUB_PERSONAL_ACCESS_TOKEN = "..." } }
]
```

## How it Works
1. **Discovery**: On startup, the `MCPClientAdapter` connects to each configured server using the specified command and arguments (typically via stdio).
2. **Tool Mapping**: The adapter fetches the list of available tools from the MCP server and maps their JSON Schema definitions into the platform's internal `Tool` format.
3. **Execution**: When the agent decides to use an MCP tool, the request is routed through the `MCPClientAdapter`, which sends a `call_tool` request to the external server.
4. **Normalization**: The result from the MCP server is normalized into a `ToolResult` and returned to the orchestrator.

## Security
- **Allowlist**: You can configure which MCP servers are allowed to connect.
- **Argument Validation**: All arguments sent to MCP tools are validated against the provided schema before being transmitted.
