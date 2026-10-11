# MCP Server Implementation

The AI Agent Platform can also act as an MCP server, exposing its internal tools to external clients (like Claude Desktop or other AI agents).

## Configuration
You can control which internal tools are exposed via the `[mcp]` section in `config/default.toml`:

```toml
[mcp]
published_tools = ["read_file", "list_directory"] # Only these tools will be visible to external clients
```

## How it Works
1. **Server Startup**: The platform can be started as an MCP server using the command `agent-platform mcp serve`.
2. **Tool Exposure**: The `MCPServerAdapter` queries the internal `ToolRegistry` and filters for tools listed in the `published_tools` allowlist.
3. **Request Handling**: When an external client calls a tool:
    - The adapter maps the MCP request to an internal tool call.
    - It executes the tool using the same security policies as if it were called by the internal agent.
    - The result is wrapped in an MCP `TextContent` response.

## Security Considerations
Exposing tools via MCP can be dangerous. The platform ensures:
- **Strict Allowlist**: No tool is exposed by default; they must be explicitly added to `published_tools`.
- **Policy Enforcement**: All external requests are subject to the same `SecurityPolicy` (e.g., workspace boundaries) as internal requests.
- **Read-Only Defaults**: It is recommended to only expose read-only tools to external clients unless a secure authentication layer is added.
