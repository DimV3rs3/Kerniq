# Security Architecture

The AI Agent Platform implements a multi-layered security model to ensure that autonomous agents operate within safe boundaries, especially when executing code or modifying the filesystem.

## 1. Workspace Isolation
All filesystem operations are restricted to a designated **Workspace**. 
- **Root Enforcement**: Every path is resolved and checked against the workspace root using `pathlib.Path.resolve()` and `is_relative_to()`.
- **Traversal Prevention**: The system explicitly blocks `..` sequences that would lead outside the root.
- **Symlink Handling**: Paths are resolved to their real location on disk before validation to prevent symlink-based escapes.

## 2. Terminal Execution Policy
The terminal tool is one of the most powerful and dangerous capabilities. It is protected by a **Policy Engine**:
- **Command Blacklisting**: A configurable list of forbidden strings (e.g., `rm -rf /`, `format C:`) is checked before execution.
- **CWD Validation**: The current working directory for any command must be within the workspace root.
- **Resource Limits**: Commands are executed with a mandatory timeout to prevent hanging processes.

## 3. Risk Levels & Approvals
Tools are categorized by risk levels: `READ_ONLY`, `LOW`, `MEDIUM`, `HIGH`, and `CRITICAL`.
- **Automatic Approval**: Low-risk tools (e.g., reading a file) are allowed automatically.
- **Manual Approval**: High or Critical risk tools trigger an `ApprovalRequest`. 
- **Human-in-the-Loop**: If an `ApprovalProvider` is configured, the system pauses execution and waits for explicit user consent. In headless mode without a provider, these actions are denied by default.

## 4. Secret Management
- **Masking**: The platform is designed to avoid logging sensitive data.
- **Configuration**: Secrets (API keys) should be provided via environment variables rather than stored in plain text in `default.toml`.

## 5. Threat Model & Limitations
This platform provides **Policy-based Security**, not OS-level sandboxing. It assumes the Python process has the permissions of the user running it. For true isolation, users are encouraged to run the platform inside a Docker container or a VM.
