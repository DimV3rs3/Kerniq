# ADR 001: Asynchronous Execution Model

**Status**: Accepted

## Context
The platform needs to handle network I/O (LLM providers), filesystem operations, and subprocess execution (terminal). These are inherently asynchronous or blocking operations.

## Decision
We use `asyncio` as the primary concurrency framework throughout the core of the platform. All provider calls, tool executions, and storage operations are defined as `async`.

## Consequences
- **Pros**: Better scalability for I/O bound tasks; consistent API across all components.
- **Cons**: Requires an async runtime (like `asyncio.run()`) at the entry point; requires careful handling of blocking synchronous calls (e.g., using `run_in_executor`).
