"""Persistent UI / agent settings (JSON under state/)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Display name -> instruction fragment for system prompt
RESPONSE_LANGUAGES = {
    "auto": "Auto (match the user)",
    "en": "English",
    "ru": "Russian",
    "uk": "Ukrainian",
    "be": "Belarusian",
    "kk": "Kazakh",
    "uz": "Uzbek",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "pl": "Polish",
    "cs": "Czech",
    "sk": "Slovak",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
    "sr": "Serbian",
    "hr": "Croatian",
    "tr": "Turkish",
    "ar": "Arabic",
    "he": "Hebrew",
    "fa": "Persian",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "ka": "Georgian",
    "hy": "Armenian",
    "az": "Azerbaijani",
}



class AgentRuntimeSettings(BaseModel):
    max_iterations: Optional[int] = 15  # null → use platform default high
    max_tokens: Optional[int] = None  # null → model/provider max (omit limit)
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    timeout_seconds: Optional[int] = 120
    workspace: str = "./workspace"
    undo_history_size: int = 100
    # How many identical replies / tool repeats to allow before loop protection stops.
    loop_retries: int = 4


class ApiModelSettings(BaseModel):
    provider: str = "lm_studio"  # id from Kerniq.models.catalog
    base_url: str = "http://localhost:1234"
    model: str = ""  # empty → first available / loaded
    api_token: str = ""  # not written to logs
    binary_path: str = ""  # Claude Code CLI path
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None  # null = auto/max
    # Editable per-provider notes. Catalog text is only the initial value.
    provider_descriptions: Dict[str, str] = Field(default_factory=dict)


class SystemPromptSettings(BaseModel):
    system_prompt: str = (
        "You are a helpful coding agent with filesystem, terminal and web tools. "
        "Work only inside the workspace. Prefer small, correct edits. "
        "You may call multiple tools in one turn (parallel tool_calls), "
        "e.g. fetch several URLs or search+fetch together."
    )
    include_tool_catalog: bool = True


class ChatSettings(BaseModel):
    streaming: bool = True
    show_reasoning_live: bool = True
    empty_response_status: bool = True
    developer_mode: bool = False  # show tool args / raw payloads in UI
    send_key: str = "enter"  # enter | shift_enter
    file_ops_only: bool = False  # UI: only show file create/edit/delete names
    aggregate_tools: bool = True  # merge consecutive identical tool names in UI
    response_language: str = "en"  # key from RESPONSE_LANGUAGES
    # read_only | low | medium | high. Critical always requires a human.
    auto_approve_up_to: str = "low"
    # plan studies the project and writes a TODO list. act edits files.
    agent_mode: str = "act"
    auto_act_after_plan: bool = True
    # Auto locks Plan|Act and asks the model whether a plan is required.
    mode_auto: bool = True
    # Do not stop until the request is actually done. After Plan, build an Act plan.
    compose_plan: bool = True


class ToolsUiSettings(BaseModel):
    fs_enabled: bool = True
    terminal_enabled: bool = True
    web_search_enabled: bool = True
    fetch_url_enabled: bool = True
    enabled_tools: Dict[str, bool] = Field(default_factory=dict)


class PluginsUiSettings(BaseModel):
    enabled: Dict[str, bool] = Field(default_factory=dict)


class UiSettings(BaseModel):
    chat: ChatSettings = Field(default_factory=ChatSettings)
    agent: AgentRuntimeSettings = Field(default_factory=AgentRuntimeSettings)
    api: ApiModelSettings = Field(default_factory=ApiModelSettings)
    prompt: SystemPromptSettings = Field(default_factory=SystemPromptSettings)
    tools: ToolsUiSettings = Field(default_factory=ToolsUiSettings)
    plugins: PluginsUiSettings = Field(default_factory=PluginsUiSettings)


class UiSettingsStore:
    FILENAME = "ui_settings.json"

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / self.FILENAME
        self._cache: Optional[UiSettings] = None

    def load(self) -> UiSettings:
        if self._cache is not None:
            return self._cache
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._cache = UiSettings(**data)
                return self._cache
            except Exception:
                pass
        self._cache = UiSettings()
        return self._cache

    def save(self, settings: Optional[UiSettings] = None) -> UiSettings:
        if settings is not None:
            self._cache = settings
        if self._cache is None:
            self._cache = UiSettings()
        tmp = self.path.with_suffix(".tmp")
        # Never leave secrets in world-readable logs; file is local state
        tmp.write_text(self._cache.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return self._cache

    def update(self, patch: Dict[str, Any]) -> UiSettings:
        current = self.load().model_dump()
        for section, values in patch.items():
            if section in current and isinstance(values, dict):
                current[section].update(values)
            else:
                current[section] = values
        self._cache = UiSettings(**current)
        return self.save()
