# API Contracts & DTOs

This document defines the stable data structures used for communication between the different layers of the AI Agent Platform.

## 1. Model Communication
The platform uses a unified format to ensure provider independence.

### Message
Used for conversation history.
- `role`: `MessageRole` (SYSTEM, USER, ASSISTANT, TOOL)
- `content`: The text content of the message.
- `tool_calls`: List of `ToolCall` objects (if role is ASSISTANT).
- `tool_call_id`: ID of the tool call this message responds to (if role is TOOL).

### ToolCall
- `id`: Unique identifier for the specific call.
- `name`: The name of the tool to be executed.
- `arguments`: A dictionary of arguments validated against the tool's schema.

### ModelRequest / ModelResponse
Wrappers for the inference process, including `GenerationOptions` (temperature, max_tokens) and `TokenUsage`.

## 2. Tool System
Tools must implement the `Tool` abstract base class.

### Tool Contract
- `tool_id`: Stable unique identifier.
- `name`: Human-readable name.
- `description`: Description used by the LLM to decide when to use the tool.
- `input_schema`: JSON Schema defining expected arguments.
- `execute(arguments, context)`: Async method returning a `ToolResult`.

### ToolResult
- `tool_call_id`: ID of the original call.
- `status`: "success" or "error".
- `output`: The raw result data.
- `human_readable`: A string representation for the LLM.

## 3. Plugin System
Plugins are managed via a manifest and a lifecycle contract.

### PluginManifest
Defined in TOML:
- `plugin_id`, `name`, `version`, `api_version`.
- `entry_point`: The Python class to instantiate.
- `capabilities`: List of provided features (e.g., "tools").

### Plugin Lifecycle
1. `initialize(context)`: Called when the plugin is loaded. Used to register tools or services.
2. `shutdown()`: Called during platform shutdown for resource cleanup.

## 4. Storage & Sessions
- **Storage**: Interface providing `get`, `put`, `delete`, and `list_keys`.
- **Session**: A record containing the task goal, workspace path, message history, and current status.
