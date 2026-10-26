"""Main project settings: agent, API, prompt, and chat.

File: state/settings.json. Tool values live in state/tools.json.
Plugin values live in state/plugins.json. This store does not touch them.
"""

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
    # When false, Plan and Act share `model`. When true, Act uses `act_model`.
    split_models: bool = False
    act_model: str = ""
    api_token: str = ""  # not written to logs
    binary_path: str = ""  # Claude Code CLI path
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None  # null = auto/max
    # Off: ask before loading next to another model. On: apply model_load_action.
    auto_model_load: bool = False
    # alongside | unload_idle | unload_busy | notify. Used only when auto is on.
    model_load_action: str = "notify"
    # Editable per-provider notes. Catalog text is only the initial value.
    provider_descriptions: Dict[str, str] = Field(default_factory=dict)


class SystemPromptSettings(BaseModel):
    system_prompt: str = (
        "You are a helpful coding agent with filesystem, terminal and web tools. "
        "Work only inside the workspace. Prefer small, correct edits. "
        "When a fact can have changed, call web_search and fetch_url before you rely on memory. "
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
    # read_only | low | medium | high | all. "all" is the developer bypass.
    auto_approve_up_to: str = "low"
    # plan studies the project and writes a TODO list. act edits files.
    agent_mode: str = "act"
    auto_act_after_plan: bool = True
    # Auto locks Plan|Act and asks the model whether a plan is required.
    mode_auto: bool = True
    # Do not stop until the request is actually done. After Plan, build an Act plan.
    compose_plan: bool = True
    # Attached files and folders outside the workspace stay read-only until this is off.
    read_only_external_attachments: bool = True


class InterfaceSettings(BaseModel):
    """Look of the local UI. Stored in the project, not in the browser."""

    layout: str = "editor"  # editor | agent
    motion: str = "on"  # on | off | auto
    blur: bool = True
    highlight: bool = True
    auto_think: bool = False
    show_notifications: bool = True
    auto_dismiss_notifications: bool = True
    theme: str = "dark"  # dark | light | system


class UiSettings(BaseModel):
    chat: ChatSettings = Field(default_factory=ChatSettings)
    agent: AgentRuntimeSettings = Field(default_factory=AgentRuntimeSettings)
    api: ApiModelSettings = Field(default_factory=ApiModelSettings)
    prompt: SystemPromptSettings = Field(default_factory=SystemPromptSettings)
    interface: InterfaceSettings = Field(default_factory=InterfaceSettings)


class UiSettingsStore:
    FILENAME = "settings.json"

    def __init__(self, state_dir: Path | str):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / self.FILENAME
        self._cache: Optional[UiSettings] = None

    def load(self) -> UiSettings:
        if self._cache is not None:
            return self._cache
        from .file import read_settings_file, settings_path
        from .secrets import open_settings, token_is_plaintext
        path = settings_path(self.state_dir)
        if not path.parent.is_dir():
            self._cache = UiSettings()
            return self._cache
        raw = read_settings_file(self.state_dir)
        existed = path.is_file()
        needs_seal = token_is_plaintext(raw)
        raw = open_settings(self.state_dir, raw)
        try:
            self._cache = UiSettings.model_validate(raw) if raw else UiSettings()
        except Exception:
            self._cache = UiSettings()
        known = self._cache.model_dump()
        if not existed or needs_seal or any(key not in raw for key in known):
            self.save()
        return self._cache

    def save(self, settings: Optional[UiSettings] = None) -> UiSettings:
        from .file import read_settings_file, write_settings_file
        from .secrets import open_settings, seal_settings
        if settings is not None:
            self._cache = settings
        if self._cache is None:
            self._cache = UiSettings()
        raw = open_settings(self.state_dir, read_settings_file(self.state_dir))
        dumped = self._cache.model_dump()
        for key in list(raw):
            if key not in dumped:
                raw.pop(key, None)
        raw.update(dumped)
        write_settings_file(self.state_dir, seal_settings(self.state_dir, raw))
        return self._cache

    def update(self, patch: Dict[str, Any]) -> UiSettings:
        current = self.load().model_dump()
        for section, values in patch.items():
            if section in current and isinstance(values, dict) and isinstance(current[section], dict):
                current[section].update(values)
            else:
                current[section] = values
        self._cache = UiSettings.model_validate(current)
        return self.save()


SettingsStore = UiSettingsStore
