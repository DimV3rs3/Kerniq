"""Where each setting lives. The model uses this. The settings screen does not."""

from __future__ import annotations

from typing import Any

# tab, focus id, English label, short hint. focus id is the control in the Web UI.
CORE_SETTINGS: tuple[tuple[str, str, str, str], ...] = (
    ("agent", "s-workspace", "Workspace", "Folder the agent edits"),
    ("agent", "s-attachments", "Attachments folder", "Where attached files are stored"),
    ("agent", "s-downloads", "Downloads folder", "Where downloaded files are stored"),
    ("agent", "s-max-iter", "Max iterations", "Maximum agent steps per run"),
    ("agent", "s-loop-retries", "Loop retries", "How many repeated replies to allow"),
    ("agent", "s-timeout", "Model response timeout", "Maximum time to wait for one model response"),
    ("agent", "s-undo-size", "Undo history size", "Editor undo steps"),
    ("agent", "s-host-freedom", "Host freedom", "Real paths and privileged commands. Developer mode, venv off"),
    ("agent", "s-allow-elevated", "Allow elevated actions", "Restart as administrator on Windows"),
    ("agent", "s-leave-venv", "Virtual environment", "Sandbox for shell commands. Off shows programs installed on this computer"),
    ("api", "s-provider", "Provider", "Which model service to call"),
    ("api", "s-base-url", "Base URL", "API address"),
    ("api", "s-api-token", "API token", "Key for the provider"),
    ("api", "s-model", "Model", "Plan model"),
    ("api", "s-split-models", "Different model for Act", "Act can use another model"),
    ("api", "s-act-model", "Act model", "Model used after a plan"),
    ("api", "s-auto-load", "Decide load and unload automatically", "What to do when another model is loaded"),
    ("api", "s-load-action", "When another model is loaded", "Load alongside, unload, or notify"),
    ("api", "s-model-sort", "Sort models", "Name, parameters, or context length"),
    ("api", "s-api-temp", "Temperature", "How varied replies are"),
    ("api", "s-api-max-tokens", "Max tokens", "How long a reply may be"),
    ("api", "s-api-context", "Context length", "Window used to load a local model"),
    ("prompt", "s-system", "System prompt", "Instructions sent with every run"),
    ("prompt", "s-include-tools", "Include tool catalog", "Tools are native definitions, not pasted into the prompt"),
    ("chat", "s-chat-streaming", "Stream responses", "Show tokens as they arrive"),
    ("chat", "s-chat-reasoning", "Show reasoning", "Show thinking blocks"),
    ("chat", "s-chat-empty", "Status on empty response", "Note when the model replies with nothing"),
    ("chat", "s-chat-debug", "Developer mode", "Show tool arguments and unlock the risk bypass"),
    ("chat", "s-parallel-tools", "Run tools in parallel", "Developer mode only"),
    ("chat", "s-send-enter", "Enter sends", "Enter sends, Shift+Enter inserts a line"),
    ("chat", "s-send-shift-enter", "Shift+Enter sends", "Enter inserts a line"),
    ("chat", "s-chat-fileops", "File ops names only", "Short file-change lines in chat"),
    ("chat", "s-chat-agg", "Merge tool calls", "Consecutive tool calls become one block"),
    ("chat", "s-mode-auto", "Auto Plan / Act", "The model decides whether a plan is needed"),
    ("chat", "s-compose-plan", "Build a plan", "First turn can only edit the TODO"),
    ("chat", "s-show-plan", "Show plan", "Plan list above the chat"),
    ("chat", "s-auto-act", "Run Act after Plan", "Act starts when the plan is written"),
    ("chat", "s-auto-approve", "Auto-approve risk", "Tools at or below this risk run without asking"),
    ("chat", "s-external-ro", "Attachments are read-only", "Outside files the user attached"),
    ("chat", "s-chat-lang", "Response language", "Language of agent replies. Not the interface language"),
    ("interface", "seg-theme", "Colour theme", "Dark, light, or match the computer"),
    ("interface", "seg-layout", "Workspace layout", "Editor and chat, or agent only"),
    ("interface", "s-agent-chat-full", "Full width chat", "Agent conversation width"),
    ("interface", "seg-motion", "Animations", "Motion in the interface"),
    ("interface", "ui-blur", "Background blur", "Dialogs blur the page"),
    ("interface", "ui-lang", "Interface language", "Language of Kerniq itself"),
    ("interface", "ui-footer", "Status footer", "Provider, model, and context in the footer"),
    ("interface", "ui-autostart", "Start when you sign in", "Open the UI at sign-in"),
    ("interface", "ui-update-kerniq", "Auto-update Kerniq", "Install a newer Kerniq release and restart"),
    ("interface", "ui-update-plugins", "Auto-update plugins", "Install newer plugin releases and restart"),
    ("interface", "ui-show-toasts", "Show notifications", "Toasts"),
    ("interface", "ui-auto-dismiss", "Dismiss notifications", "Toasts leave on their own"),
    ("interface", "ui-auto-think", "Auto-expand reasoning", "Open the reasoning block while the model thinks"),
    ("interface", "ui-hl", "Syntax highlighting", "Colour code in the editor"),
    ("plugins", "plugin-repo", "Install a plugin", "Search or paste owner/repo"),
    ("plugins", "s-show-hidden-plugins", "Show hidden plugins", "Plugins that are not listed"),
    ("tools", "s-tools-list", "Tools", "Turn tools on and set their options"),
)

_TAB_LABEL = {
    "agent": "Agent",
    "api": "API & model",
    "prompt": "System prompt",
    "chat": "Chat",
    "interface": "Interface",
    "tools": "Tools",
    "plugins": "Plugins",
}


def _row(tab: str, focus: str, label: str, hint: str) -> dict[str, str]:
    return {
        "tab": tab,
        "tab_label": _TAB_LABEL.get(tab, tab),
        "id": focus,
        "label": label,
        "hint": hint,
        "link": f"[[setting:{tab}:{focus}|{label}]]",
    }


def _plugin_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        import importlib.util
        import tomllib
        from pathlib import Path

        from Kerniq.devtools.paths import find_plugins_dirs
        from Kerniq.plugins.manager import normalize_manifest_data
    except Exception:
        return rows
    seen = set()
    for root in find_plugins_dirs():
        if not root.is_dir():
            continue
        for folder in sorted(p for p in root.iterdir() if p.is_dir() and (p / "manifest.toml").is_file()):
            try:
                with open(folder / "manifest.toml", "rb") as handle:
                    raw = normalize_manifest_data(tomllib.load(handle))
                plugin_id = str(raw.get("plugin_id") or folder.name)
                if plugin_id in seen or plugin_id == "plugin_web_ui":
                    continue
                seen.add(plugin_id)
                title = str(raw.get("name") or plugin_id)
                main_py = folder / "main.py"
                if not main_py.is_file():
                    continue
                name = "kerniq_catalog_" + folder.name
                spec = importlib.util.spec_from_file_location(name, main_py)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                cls = getattr(module, "PluginImpl", None)
                if cls is None:
                    continue
                schema = cls().settings_schema()
                fields = getattr(schema, "fields", None) or []
                tab = "plug-" + plugin_id
                _TAB_LABEL[tab] = title
                if not fields:
                    rows.append(_row(tab, plugin_id, title, "Plugin settings"))
                    continue
                for field in fields:
                    key = str(getattr(field, "key", "") or "")
                    if not key:
                        continue
                    rows.append(_row(
                        tab,
                        key,
                        str(getattr(field, "label", "") or key),
                        str(getattr(field, "description", "") or title),
                    ))
            except Exception:
                continue
    return rows


def search_settings(query: str = "", *, limit: int = 12) -> dict[str, Any]:
    words = [part for part in (query or "").lower().split() if part]
    rows = [_row(*item) for item in CORE_SETTINGS]
    rows.extend(_plugin_rows())
    if words:
        matched = []
        for row in rows:
            hay = " ".join((row["label"], row["hint"], row["tab_label"], row["id"], row["tab"])).lower()
            if all(word in hay for word in words):
                matched.append(row)
    else:
        matched = rows
    total = len(matched)
    shown = matched[: max(1, int(limit or 12))]
    lines = []
    for row in shown:
        lines.append(f"{row['label']} – {row['tab_label']}. {row['hint']}. {row['link']}")
    note = ""
    if total > len(shown):
        note = f"\n{total - len(shown)} more. Ask again with a narrower query."
    if not shown:
        text = "No setting matches. Ask with different words, or leave the query empty to list them."
    else:
        text = (
            "Put these tokens in the reply unchanged. Each one opens that setting and highlights it.\n"
            + "\n".join(lines)
            + note
        )
    return {"matches": shown, "total": total, "text": text}
