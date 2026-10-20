"""Provider catalog: what each backend needs, and how the UI should ask for it.

The Web UI renders ``fields`` for the selected provider and hides the rest.
Do not put secrets in logs. Defaults are public endpoints, not credentials.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(
    key: str,
    label: str,
    type_: str,
    *,
    required: bool = False,
    default: str = "",
    help_: str = "",
    placeholder: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "type": type_,
        "required": required,
        "default": default,
        "help": help_,
        "placeholder": placeholder,
    }


_MODEL = _f(
    "model",
    "model",
    "model",
    help_="Leave empty to use the first model the provider returns.",
    placeholder="(auto)",
)

PROVIDER_SPECS: List[Dict[str, Any]] = [
    {
        "id": "lm_studio",
        "label": "LM Studio",
        "kind": "lm_studio",
        "tool_calls": True,
        "default_base_url": "http://127.0.0.1:1234",
        "blurb": "Local server. Chat uses OpenAI-compatible POST /v1/chat/completions. Load and unload use /api/v1/models.",
        "fields": [
            _f(
                "base_url",
                "Base URL",
                "url",
                default="http://127.0.0.1:1234",
                help_="LM Studio local server. No key unless you turned auth on.",
            ),
            _f(
                "api_token",
                "API token",
                "secret",
                required=False,
                help_="Optional. Sent as Authorization: Bearer.",
            ),
            _MODEL,
        ],
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "http://127.0.0.1:11434/v1",
        "blurb": "Local Ollama OpenAI-compatible API. No key. Free.",
        "fields": [
            _f(
                "base_url",
                "Base URL",
                "url",
                default="http://127.0.0.1:11434/v1",
                help_="Default is http://127.0.0.1:11434/v1",
            ),
            _MODEL,
        ],
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://api.deepseek.com/v1",
        "blurb": "Only an API key. Models are loaded from the key (deepseek-chat, deepseek-reasoner).",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="From platform.deepseek.com. The key is enough; the base URL is fixed.",
                placeholder="sk-...",
            ),
            _MODEL,
        ],
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://openrouter.ai/api/v1",
        "headers": {"HTTP-Referer": "https://kerniq.local", "X-Title": "Kerniq"},
        "blurb": "One key, many models including free ones (id ends with :free).",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="From openrouter.ai/keys.",
            ),
            _MODEL,
        ],
    },
    {
        "id": "openai",
        "label": "OpenAI (ChatGPT API)",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://api.openai.com/v1",
        "blurb": "Official API key from platform.openai.com. A ChatGPT Plus login is not an API and is not used here.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="Create a key at platform.openai.com/api-keys. ChatGPT.com session login cannot drive this agent.",
                placeholder="sk-...",
            ),
            _MODEL,
        ],
    },
    {
        "id": "anthropic",
        "label": "Claude (Anthropic API)",
        "kind": "anthropic",
        "tool_calls": True,
        "default_base_url": "https://api.anthropic.com",
        "blurb": "Anthropic Messages API. Key from console.anthropic.com. Native tool use.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="Sent as x-api-key. Not the Claude.ai password.",
                placeholder="sk-ant-...",
            ),
            _MODEL,
        ],
    },
    {
        "id": "claude_code",
        "label": "Claude Code",
        "kind": "claude_code",
        "tool_calls": False,
        "default_binary": "claude",
        "blurb": "Path to the Claude Code CLI. Auth is your local `claude` login, not an API key pasted here. Text only: Kerniq tools are not delegated to the CLI (it is started in plan permission mode).",
        "fields": [
            _f(
                "binary_path",
                "Claude CLI path",
                "path",
                required=True,
                default="claude",
                help_="Executable path, or `claude` if it is on PATH.",
                placeholder="claude",
            ),
            _f(
                "model",
                "Model alias",
                "model",
                help_="Optional --model (sonnet, opus, haiku).",
            ),
        ],
    },
    {
        "id": "gemini",
        "label": "Gemini",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "blurb": "Google AI Studio key. Uses the OpenAI-compatible Gemini endpoint. Free tier exists on that key.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="From aistudio.google.com/apikey.",
            ),
            _MODEL,
        ],
    },
    {
        "id": "groq",
        "label": "Groq (free tier)",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://api.groq.com/openai/v1",
        "blurb": "Free-tier OpenAI-compatible API. Key from console.groq.com.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="From console.groq.com.",
            ),
            _MODEL,
        ],
    },
    {
        "id": "mistral",
        "label": "Mistral",
        "kind": "openai",
        "tool_calls": True,
        "default_base_url": "https://api.mistral.ai/v1",
        "blurb": "API key from console.mistral.ai. Experiment tier is free for some keys.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "secret",
                required=True,
                help_="From console.mistral.ai.",
            ),
            _MODEL,
        ],
    },
    {
        "id": "mock",
        "label": "Mock",
        "kind": "mock",
        "tool_calls": True,
        "blurb": "Offline scripted provider. No network and no key.",
        "fields": [],
    },
]


def provider_ids() -> List[str]:
    return [s["id"] for s in PROVIDER_SPECS]


def spec_by_id(provider_id: str) -> Optional[Dict[str, Any]]:
    wanted = (provider_id or "").strip()
    for spec in PROVIDER_SPECS:
        if spec["id"] == wanted:
            return spec
    return None


def public_specs() -> List[Dict[str, Any]]:
    """Catalog safe to send to the browser (no secrets)."""
    out = []
    for spec in PROVIDER_SPECS:
        out.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "kind": spec["kind"],
                "tool_calls": bool(spec.get("tool_calls")),
                "blurb": spec.get("blurb") or "",
                "fields": list(spec.get("fields") or []),
            }
        )
    return out
