# AI Agent Platform - Architectural Overview

## 1. Goal
The goal is to provide a modular, extensible foundation for autonomous AI agents. The platform separates the core orchestration logic from specific model providers, tools, and plugins.

## 2. Core Components
- **Agent Facade**: Public entry point for running tasks.
- **Orchestrator**: Manages the execution loop (Plan -> Model -> Tool -> Verify).
- **Model Router & Providers**: Abstracts LLM interactions. Supports multiple providers (LM Studio, OpenAI-compatible, Mock).
- **Tool Registry & Execution**: Manages a set of tools with strict JSON Schema validation and security policies.
- **Plugin System**: Allows extending the platform with new tools and services via manifests.
- **MCP Adapter**: Integrates Model Context Protocol for external tool discovery and exposure.
- **Session & Storage**: Persists agent state, history, and results.
- **Security Engine**: Enforces workspace boundaries and requires approvals for high-risk actions.

## 3. Dependency Flow
`Interfaces` -> `Core` -> `Providers/Tools/Plugins` (via interfaces)
The Core depends only on abstract contracts defined in the `interfaces` layer. Concrete implementations are injected at runtime via registries.

## 4. Execution Lifecycle
1. **Task Initiation**: User provides a task and workspace.
2. **Session Setup**: A session is created or restored from storage.
3. **Orchestration Loop**:
    - Context preparation (ContextManager).
    - Model selection (ModelRouter).
    - Inference (ModelProvider).
    - Tool Call Analysis: If the model requests tools, they are validated against security policies.
    - Execution: Tools are executed within the workspace.
    - Feedback: Results are fed back into the context.
4. **Verification**: The Verifier checks if the task goals are met.
5. **Completion**: Session is saved and result returned.

## 5. Security Model
- **Workspace Isolation**: All file operations are relative to a root directory; absolute paths and `..` are blocked.
- **Risk Levels**: Tools are categorized by risk (READ_ONLY, LOW, MEDIUM, HIGH, CRITICAL).
- **Approval Provider**: High-risk tools require explicit human approval in interactive mode or fail in headless mode.
