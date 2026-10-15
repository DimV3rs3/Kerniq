"""Write a machine-local MCP client snippet.

The file is generated from this interpreter and this workspace. It is not
committed, so a checkout on another machine does not keep someone else's paths.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional


def mcp_server_spec(workspace: Path) -> dict:
    return {
        "command": sys.executable,
        "args": ["-m", "Kerniq", "mcp", "serve", "--workspace", str(Path(workspace).resolve())],
    }


def write_local_mcp_config(workspace: Path, state_dir: Path) -> Path:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "mcp.client.json"
    doc = {"mcpServers": {"kerniq": mcp_server_spec(workspace)}}
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


def install_lmstudio_mcp(workspace: Path, home: Optional[Path] = None) -> tuple[bool, str]:
    """Merge Kerniq into ~/.lmstudio/mcp.json when that directory already exists."""
    root = Path(home) if home is not None else Path.home()
    folder = root / ".lmstudio"
    if not folder.is_dir():
        return False, f"LM Studio config dir not found: {folder}"
    path = folder / "mcp.json"
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        current = {}
    if not isinstance(current, dict):
        current = {}
    servers = current.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    servers["kerniq"] = mcp_server_spec(workspace)
    current["mcpServers"] = servers
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return True, str(path)
