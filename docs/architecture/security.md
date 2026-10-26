# Security Architecture

Kerniq enforces a **policy**, not an operating-system sandbox. The process has
the same filesystem and network rights as the user who started it. Docker or a
VM is required if those OS rights themselves must be limited. Do not describe
the shell tool as a sandbox.

## 1. Workspace isolation

Filesystem tools resolve paths with `Path.resolve()` (symlinks included) and
reject anything that is not under the workspace root. NUL bytes and UNC prefixes
are rejected before resolution. `move_file` checks both the source and the
destination. Zip extraction skips members whose resolved path leaves the
workspace.

`strict_attachments` (off by default) limits file tools to `allowed_files` on
the current task.

## 2. Terminal policy

`run_command` is critical risk. Without an approval provider the call is
denied. The shell string is still checked after approval:

- absolute paths, drive letters, UNC, `..`, `file://`, and home/env paths
- PowerShell `-EncodedCommand` / `Invoke-Expression` and a few obfuscation forms
- a configurable denylist, matched after quotes and spaces are folded
- outbound network utilities unless `security.allow_terminal_network = true`

On Linux the command is still a shell (`bash -c` equivalent via
`create_subprocess_shell`) because pipelines are part of the coding workflow.
A blacklist cannot see a path built at runtime inside `python -c` or similar.
That remaining hole is accepted and documented; it is not closed by substring
filters. Credential-like environment variables are removed from the child
environment. A timeout kills the process. The exit code is returned as an error
when it is non-zero.

## 3. Risk and approval

Risk is the maximum of the tool's own `risk_level` and a fixed floor
(`delete_file` high, `run_command` critical). A caller cannot lower it.

- **Critical always asks a human**, in the console and in the Web UI.
  Per-tool auto-accept does not apply.
- Other risks are allowed when they are at or below `security.auto_approve_up_to`
  (default `low`) or when that tool's `auto_accept` setting is on.
- The Web UI has the same ceiling under Chat settings. The console uses
  `ConsoleApprovalProvider` for every `kerniq run`.
- MCP publishes tools dynamically. An empty `published_tools` list means
  "whatever the policy would run with no human". It is not a snapshot of the
  tools that existed when the config was written. Critical tools are not
  auto-published. `kerniq mcp install` writes a config that uses this
  machine's Python, so it is not a hardcoded path from another computer.

## 3.1 Shell holes a stronger model will try

Backticks and `^` are stripped before the checks, so `` -En`codedCommand ``
does not hide the flag. Inline eval (`python -c`, `node -e`, `bash -c`,
`cmd /c`) is denied: a script file inside the workspace is the allowed path.
A drive built as `'C'+':\Windows'` still contains `:\` and is denied.

A symlink inside the workspace that points outside blocks `run_command` until
it is removed. Filesystem tools already refuse to follow such a link.

What remains: a normal `python script.py` runs as the OS user. The shell is
not a sandbox. Container isolation is still the way to remove that right.

## 4. Secrets and network

API tokens are read from the environment (`LM_API_TOKEN` and similar), not
printed by `doctor` beyond a boolean. Shell children do not inherit variables
whose names look like secrets. The Web UI binds to `127.0.0.1` unless server
mode is turned on. Do not enable server mode on an untrusted network.

## 5. Indirect prompt injection

Tool results and file contents are passed to the model as the facts of the task.
They are not wrapped as untrusted data, because that made the model ignore real
findings. The context compactor still refuses to follow instructions that appear
inside a transcript, and it keeps tool results as facts. That is a mitigation,
not a guarantee that a model will ignore a hostile page.
