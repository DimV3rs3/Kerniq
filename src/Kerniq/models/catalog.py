"""Provider catalog: what each backend needs, and how the UI should ask for it.

The Web UI renders ``fields`` for the selected provider and hides the rest.
Do not put secrets in logs. Defaults are public endpoints, not credentials.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(
    key: str,
    label: str,
    label_ru: str,
    type_: str,
    *,
    required: bool = False,
    default: str = "",
    help_: str = "",
    help_ru: str = "",
    placeholder: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "label_ru": label_ru,
        "type": type_,
        "required": required,
        "default": default,
        "help": help_,
        "help_ru": help_ru,
        "placeholder": placeholder,
    }


_MODEL = _f(
    "model",
    "Model",
    "Модель",
    "model",
    help_="Leave empty to use the first model the provider returns.",
    help_ru="Пусто — первая модель, которую вернёт провайдер.",
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
        "blurb_ru": "Локальный сервер. Чат — OpenAI-совместимый POST /v1/chat/completions. Загрузка моделей — /api/v1/models.",
        "fields": [
            _f(
                "base_url",
                "Base URL",
                "Base URL",
                "url",
                default="http://127.0.0.1:1234",
                help_="LM Studio local server. No key unless you turned auth on.",
                help_ru="Локальный сервер LM Studio. Ключ нужен только если включена авторизация.",
            ),
            _f(
                "api_token",
                "API token",
                "API-токен",
                "secret",
                required=False,
                help_="Optional. Sent as Authorization: Bearer.",
                help_ru="Необязательно. Уходит как Authorization: Bearer.",
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
        "blurb_ru": "Локальный Ollama, OpenAI-совместимый API. Ключ не нужен.",
        "fields": [
            _f(
                "base_url",
                "Base URL",
                "Base URL",
                "url",
                default="http://127.0.0.1:11434/v1",
                help_="Default is http://127.0.0.1:11434/v1",
                help_ru="По умолчанию http://127.0.0.1:11434/v1",
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
        "blurb_ru": "Только API-ключ. Список моделей подтягивается по ключу.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="From platform.deepseek.com. The key is enough; the base URL is fixed.",
                help_ru="С platform.deepseek.com. Ключа достаточно, адрес API фиксированный.",
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
        "blurb_ru": "Один ключ и много моделей, включая бесплатные (id заканчивается на :free).",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="From openrouter.ai/keys.",
                help_ru="С openrouter.ai/keys.",
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
        "blurb_ru": "Официальный ключ с platform.openai.com. Вход в аккаунт ChatGPT Plus — это не API, Kerniq его не использует.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="Create a key at platform.openai.com/api-keys. ChatGPT.com session login cannot drive this agent.",
                help_ru="Ключ создаётся на platform.openai.com/api-keys. Сессия chatgpt.com сюда не подключается.",
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
        "blurb_ru": "Anthropic Messages API. Ключ с console.anthropic.com. Нативные tool use.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="Sent as x-api-key. Not the Claude.ai password.",
                help_ru="Уходит как x-api-key. Это не пароль от claude.ai.",
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
        "blurb_ru": "Путь к CLI Claude Code. Авторизация — локальный вход `claude`, не API-ключ. Только текст: инструменты Kerniq в CLI не отдаются (запуск в permission mode plan).",
        "fields": [
            _f(
                "binary_path",
                "Claude CLI path",
                "Путь к claude",
                "path",
                required=True,
                default="claude",
                help_="Executable path, or `claude` if it is on PATH.",
                help_ru="Путь к исполняемому файлу или `claude`, если он в PATH.",
                placeholder="claude",
            ),
            _f(
                "model",
                "Model alias",
                "Псевдоним модели",
                "model",
                help_="Optional --model (sonnet, opus, haiku).",
                help_ru="Необязательный --model (sonnet, opus, haiku).",
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
        "blurb_ru": "Ключ Google AI Studio. OpenAI-совместимый endpoint Gemini. У ключа есть бесплатный уровень.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="From aistudio.google.com/apikey.",
                help_ru="С aistudio.google.com/apikey.",
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
        "blurb_ru": "Бесплатный уровень, OpenAI-совместимый API. Ключ с console.groq.com.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="From console.groq.com.",
                help_ru="С console.groq.com.",
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
        "blurb_ru": "Ключ с console.mistral.ai. У части ключей есть бесплатный experiment-уровень.",
        "fields": [
            _f(
                "api_token",
                "API key",
                "API-ключ",
                "secret",
                required=True,
                help_="From console.mistral.ai.",
                help_ru="С console.mistral.ai.",
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
        "blurb_ru": "Офлайн-провайдер без сети и без ключа.",
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
                "blurb_ru": spec.get("blurb_ru") or "",
                "fields": list(spec.get("fields") or []),
            }
        )
    return out
