# Architecture Lifecycle

This document describes the lifecycles of key components within the AI Agent Platform.

## 1. Task Lifecycle
A task is the primary unit of work for an agent.
`CREATED -> RUNNING -> (VERIFYING) -> [SUCCESS | FAILED | CANCELLED | LIMIT_REACHED]`

- **CREATED**: The task is defined with a goal and workspace.
- **RUNNING**: The Orchestrator is executing the loop: Model Request -> Tool Execution -> Context Update.
- **VERIFYING**: After the model suggests it has finished, the Verifier checks the result against criteria.
- **SUCCESS**: Task completed and verified.
- **FAILED**: Task failed due to errors or verification failure after retries.
- **CANCELLED**: User or system explicitly stopped the task.
- **LIMIT_REACHED**: Maximum iterations or tokens exceeded.

## 2. Model Session Lifecycle
`NEW -> OPEN -> IN_USE -> STOPPING -> CLOSED`

- **NEW**: Session object created but not yet connected to a provider.
- **OPEN**: Connection established with the LLM provider.
- **IN_USE**: Active inference requests are being processed.
- **STOPPING**: Graceful shutdown initiated.
- **CLOSED**: Resources released, connection closed.

## 3. Plugin Lifecycle
`DISCOVERED -> VALIDATED -> INITIALIZED -> AVAILABLE -> REGISTERED -> STOPPING -> STOPPED`

- **DISCOVERED**: Plugin found in the search paths via manifest.
- **VALIDATED**: Manifest checked for compatibility and required fields.
- **INITIALIZED**: `plugin.initialize(context)` called.
- **AVAILABLE**: Plugin is ready to provide tools or services.
- **REGISTERED**: Tools from the plugin are added to the global Tool Registry.
- **STOPPING**: Shutdown sequence initiated.
- **STOPPED**: Resources cleaned up.

## 4. MCP Connection Lifecycle
`CONFIGURED -> CONNECTING -> CONNECTED -> DISCONNECTING -> CLOSED`

- **CONFIGURED**: Server details loaded from config.
- **CONNECTING**: Transport layer establishing connection.
- **CONNECTED**: Handshake complete, tools discovered and mapped to internal API.
- **DISCONNECTING**: Closing the transport.
- **CLOSED**: Connection terminated.
