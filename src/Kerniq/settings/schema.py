"""Validated configuration schema."""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pathlib import Path


class ApplicationSettings(BaseModel):
    name: str = "AI Agent Platform"
    version: str = "0.1.0"
    workspace_root: Path = Path("./workspace")
    auto_install_deps: bool = True


class LoggingSettings(BaseModel):
    level: str = "INFO"
    log_file: Path = Path("./logs/platform.jsonl")
    enable_tracing: bool = True


class RuntimeSettings(BaseModel):
    max_iterations: int = 15
    max_tool_calls: int = 20
    timeout_seconds: int = 120
    retry_limit: int = 3


class ModelSettings(BaseModel):
    default_provider: str = "lm_studio"
    default_model: str = ""
    temperature: float = 0.7
    max_tokens: Optional[int] = 4096
    providers: Dict[str, Any] = Field(default_factory=dict)


class SecuritySettings(BaseModel):
    require_approval_for_high_risk: bool = True
    allowed_terminal_commands: List[str] = Field(default_factory=list)
    disallowed_terminal_commands: List[str] = Field(
        default_factory=lambda: ["rm -rf /", "format C:", "mkfs"]
    )
    allow_terminal_network: bool = False
    strict_attachments: bool = False
    # Auto-approve tools at or below this risk. Critical always asks.
    auto_approve_up_to: str = "low"


class ToolsConfigSettings(BaseModel):
    web_search_enabled: bool = True
    fetch_url_enabled: bool = True
    terminal_enabled: bool = True
    fs_enabled: bool = True


class MCPSettings(BaseModel):
    enabled: bool = False
    servers: List[Dict[str, Any]] = Field(default_factory=list)
    published_tools: List[str] = Field(default_factory=list)


class StorageSettings(BaseModel):
    type: str = "json"
    sessions_dir: Path = Path("./sessions")
    state_dir: Path = Path("./state")


class UISettings(BaseModel):
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 8765


class PlatformConfig(BaseModel):
    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    models: ModelSettings = Field(default_factory=ModelSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    tools: ToolsConfigSettings = Field(default_factory=ToolsConfigSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    ui: UISettings = Field(default_factory=UISettings)

    @field_validator(
        "application", "logging", "runtime", "models", "security",
        "tools", "mcp", "storage", "ui", mode="before",
    )
    @classmethod
    def validate_section(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return v
        return v
