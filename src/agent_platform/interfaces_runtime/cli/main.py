"""AI Agent Platform CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from agent_platform.bootstrap import ensure_dependencies, format_bootstrap_report
from agent_platform.core.agent import Agent
from agent_platform.models.providers.mock import MockProvider
from agent_platform.models.providers.lm_studio import LMStudioProvider
from agent_platform.models.system_info import collect_system_info, recommend_for_lm_studio
from agent_platform.tools.registry import ToolRegistry
from agent_platform.tools.filesystem import FileSystemTools
from agent_platform.tools.terminal import TerminalTools
from agent_platform.tools.web_search import WebSearchTool, FetchUrlTool
from agent_platform.tools.settings import ToolSettingsStore
from agent_platform.security.policy import SecurityPolicy
from agent_platform.settings.loader import SettingsProvider
from agent_platform.core.verifier import BasicVerifier
from agent_platform.storage.json_store import JsonStorage
from agent_platform.sessions.manager import SessionManager
from agent_platform.plugins.manager import PluginManager
from agent_platform.plugins.base import PluginContext

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("cli")


def _build_registry(config, workspace: Path, tool_settings_store: ToolSettingsStore):
    ts = tool_settings_store.settings
    registry = ToolRegistry()
    policy = SecurityPolicy(
        workspace_root=workspace,
        disallowed_commands=config.security.disallowed_terminal_commands,
        require_approval_for_high_risk=config.security.require_approval_for_high_risk,
    )
    if ts.fs_enabled:
        for tool in FileSystemTools(workspace=str(workspace)).get_tools():
            registry.register_tool(tool)
    if ts.terminal_enabled:
        registry.register_tool(TerminalTools(workspace, policy))
    if ts.web_search_enabled:
        registry.register_tool(
            WebSearchTool(
                enabled=True,
                max_results=ts.web_search_max_results,
                timeout=ts.web_search_timeout,
            )
        )
    if ts.fetch_url_enabled:
        registry.register_tool(FetchUrlTool(enabled=True, timeout=ts.fetch_url_timeout))
    return registry, policy


async def run_agent(args: argparse.Namespace, config) -> int:
    workspace_path = Path(args.workspace or str(config.application.workspace_root))
    workspace_path.mkdir(parents=True, exist_ok=True)
    store = ToolSettingsStore(config.storage.state_dir)
    registry, policy = _build_registry(config, workspace_path, store)

    provider_name = args.provider or config.models.default_provider
    if provider_name == "lm_studio":
        ls_config = config.models.providers.get("lm_studio", {})
        provider = LMStudioProvider(
            base_url=ls_config.get("base_url", "http://localhost:1234"),
            api_key=ls_config.get("api_key"),
            model=ls_config.get("model") or config.models.default_model or None,
        )
        if not await provider.check_connection():
            logger.warning("LM Studio not reachable — falling back to mock")
            if args.provider == "lm_studio":
                print("ERROR: LM Studio is not reachable. Start it or use --provider mock.", file=sys.stderr)
                return 1
            provider = MockProvider()
            provider_name = "mock"
    elif provider_name == "mock":
        provider = MockProvider()
    else:
        logger.error("Unsupported provider: %s", provider_name)
        return 1

    agent = Agent(provider, registry)
    agent.orchestrator.security_policy = policy
    agent.orchestrator.verifier = BasicVerifier()
    agent.orchestrator.max_iterations = config.runtime.max_iterations

    print(f"Provider: {provider_name} | Workspace: {workspace_path}")
    print(f"Tools: {[t.name for t in registry.list_tools()]}")
    lang = "auto"
    try:
        from agent_platform.settings.ui_store import UiSettingsStore
        lang = UiSettingsStore().load().chat.response_language or "auto"
    except Exception:
        pass
    result = await agent.run(args.task, workspace=str(workspace_path, response_language=lang))
    print(f"\nAgent Result:\n{result}")
    return 0


async def cmd_doctor(config) -> int:
    print("=== Agent Platform Doctor ===")
    report = ensure_dependencies(auto_install=config.application.auto_install_deps)
    print(format_bootstrap_report(report))

    sysinfo = collect_system_info()
    print("\n--- System ---")
    for k, v in sysinfo.to_dict().items():
        print(f"  {k}: {v}")

    ls_cfg = config.models.providers.get("lm_studio", {})
    ls = LMStudioProvider(
        base_url=ls_cfg.get("base_url", "http://localhost:1234"),
        api_key=ls_cfg.get("api_key"),
        model=ls_cfg.get("model") or config.models.default_model or None,
    )
    print("\n--- LM Studio ---")
    health = await ls.health_report()
    print(f"  Host: {health.get('host') or health.get('base_url')}")
    print(f"  Models URL: {health.get('models_url')}")
    print(f"  Chat URL: {health.get('chat_url')}")
    print(f"  Auth token set: {health.get('auth')}")
    print(f"  Reachable: {health['reachable']}")
    if health.get("models"):
        print(f"  Models ({len(health['models'])}):")
        for m in health["models"]:
            print(f"    - {m.get('id')}")
    if health.get("error"):
        print(f"  Error: {health['error']}")
    if health.get("hint"):
        print(f"  Hint: {health['hint']}")

    rec = recommend_for_lm_studio(sysinfo, health.get("models") or [])
    print("\n--- Recommendations ---")
    print(f"  Size hint: {rec['size_hint']}")
    if rec.get("preferred_model"):
        print(f"  Preferred model: {rec['preferred_model']}")
    for line in rec["recommendations"]:
        print(f"  • {line}")

    store = ToolSettingsStore(config.storage.state_dir)
    ts = store.settings
    print("\n--- Tool settings ---")
    print(
        f"  fs={ts.fs_enabled} terminal={ts.terminal_enabled} "
        f"web_search={ts.web_search_enabled} fetch_url={ts.fetch_url_enabled}"
    )
    print(f"  state file: {store.path}")
    print(f"\nWorkspace: {config.application.workspace_root}")
    print(f"Default provider: {config.models.default_provider}")
    print("Doctor finished.")
    return 0 if report.ok else 1


async def async_main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="AI Agent Platform CLI")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run an agent task")
    run_parser.add_argument("--task", type=str, required=True)
    run_parser.add_argument("--workspace", type=str)
    run_parser.add_argument("--provider", type=str, help="lm_studio | mock")

    subparsers.add_parser("doctor", help="System health, deps, LM Studio")

    config_parser = subparsers.add_parser("config")
    config_sub = config_parser.add_subparsers(dest="action")
    config_sub.add_parser("validate")

    model_parser = subparsers.add_parser("models")
    model_parser.add_argument("action", choices=["list", "check", "loaded", "load", "unload-all"])
    model_parser.add_argument("--model", default=None, help="Model key for load")
    model_parser.add_argument("--alongside", action="store_true", help="Load without unloading others")

    tool_parser = subparsers.add_parser("tools")
    tool_sub = tool_parser.add_subparsers(dest="action")
    tool_sub.add_parser("list")
    tool_sub.add_parser("settings")
    set_parser = tool_sub.add_parser("set")
    set_parser.add_argument("key")
    set_parser.add_argument("value")

    plugin_parser = subparsers.add_parser("plugins")
    plugin_sub = plugin_parser.add_subparsers(dest="action")
    plugin_sub.add_parser("list")
    plugin_sub.add_parser("validate")
    ui_parser = plugin_sub.add_parser("ui")
    ui_parser.add_argument("--host", default=None)
    ui_parser.add_argument("--port", type=int, default=None)

    session_parser = subparsers.add_parser("sessions")
    session_sub = session_parser.add_subparsers(dest="action")
    session_sub.add_parser("list")
    show_session = session_sub.add_parser("show")
    show_session.add_argument("id", type=str)

    settings_parser = subparsers.add_parser("settings", help="Manage component settings")
    settings_sub = settings_parser.add_subparsers(dest="action")
    settings_sub.add_parser("reset", help="Reset tool/plugin settings to defaults")
    settings_sub.add_parser("show", help="Show component settings files")
    lang_list = settings_sub.add_parser("languages", help="List response languages")
    lang_set = settings_sub.add_parser("language", help="Get/set response language (english name or code)")
    lang_set.add_argument("value", nargs="?", default=None, help="e.g. Russian, ru, English, auto")

    mcp_parser = subparsers.add_parser("mcp")
    mcp_sub = mcp_parser.add_subparsers(dest="action")
    mcp_sub.add_parser("validate")
    mcp_sub.add_parser("serve")

    args = parser.parse_args(argv)

    if args.version or args.command is None:
        from agent_platform import __version__
        if args.version:
            print(__version__)
            return 0
        parser.print_help()
        return 0

    try:
        config = SettingsProvider().config
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    if config.application.auto_install_deps and args.command in ("run", "doctor", "plugins"):
        ensure_dependencies(auto_install=True)

    storage = JsonStorage(Path(config.storage.sessions_dir))
    sm = SessionManager(storage)
    tool_store = ToolSettingsStore(config.storage.state_dir)

    def plugin_ctx_factory():
        return PluginContext(
            logger=logging.getLogger("plugin"),
            config=config,
            event_bus=None,
            tool_registry=ToolRegistry(),
        )

    pm = PluginManager(context_factory=plugin_ctx_factory)

    if args.command == "run":
        return await run_agent(args, config)
    if args.command == "doctor":
        return await cmd_doctor(config)
    if args.command == "config":
        if args.action == "validate":
            print("Configuration is valid.")
            print(f"  default_provider={config.models.default_provider}")
            print(f"  workspace={config.application.workspace_root}")
            print(f"  auto_install_deps={config.application.auto_install_deps}")
            return 0
        print("Usage: config validate")
        return 1
    if args.command == "models":
        if args.action == "list":
            print(f"Providers: mock, lm_studio (default: {config.models.default_provider})")
            ls_cfg = config.models.providers.get("lm_studio", {})
            ls = LMStudioProvider(
                base_url=ls_cfg.get("base_url", "http://localhost:1234"),
                model=ls_cfg.get("model") or config.models.default_model or None,
            )
            if await ls.check_connection():
                models = await ls.list_models()
                print(f"LM Studio models ({len(models)}):")
                for m in models:
                    print(f"  - {m.get('id')}")
            else:
                print("LM Studio: unreachable")
            return 0
        if args.action == "check":
            return await cmd_doctor(config)
        ls_cfg = config.models.providers.get("lm_studio", {})
        ls = LMStudioProvider(
            base_url=ls_cfg.get("base_url", "http://localhost:1234"),
            model=ls_cfg.get("model") or config.models.default_model or None,
            timeout=float(ls_cfg.get("timeout", config.runtime.timeout_seconds or 600)),
        )
        if args.action == "loaded":
            loaded = await ls.loaded_instances()
            if not loaded:
                print("No models loaded")
            for item in loaded:
                print(f"  {item.get('model')}  instance={item.get('instance_id') or item.get('id')}")
            return 0
        if args.action == "unload-all":
            res = await ls.unload_all()
            print(f"Unloaded: {len(res)}")
            return 0
        if args.action == "load":
            model = args.model or ls_cfg.get("model") or config.models.default_model
            if not model:
                print("Specify --model")
                return 1
            loaded = await ls.loaded_instances()
            if loaded and not args.alongside:
                print("WARNING: other models loaded:")
                for item in loaded:
                    print(f"  {item.get('model')}")
                print("Use --alongside to load next to them, or models unload-all first.")
                return 2
            print(f"Loading {model}...")
            res = await ls.load_model(model)
            print(res)
            return 0
    if args.command == "tools":
        if args.action == "list":
            ws = Path(config.application.workspace_root)
            reg, _ = _build_registry(config, ws, tool_store)
            for t in reg.list_tools():
                print(f"  {t.name:20}  {t.tool_id:20}  {t.description[:60]}")
            return 0
        if args.action == "settings":
            ts = tool_store.settings
            for k, v in ts.model_dump().items():
                print(f"  {k} = {v}")
            print(f"\nSaved at: {tool_store.path}")
            return 0
        if args.action == "set":
            key, value = args.key, args.value
            if value.lower() in ("true", "1", "yes"):
                parsed: object = True
            elif value.lower() in ("false", "0", "no"):
                parsed = False
            else:
                try:
                    parsed = int(value)
                except ValueError:
                    try:
                        parsed = float(value)
                    except ValueError:
                        parsed = value
            tool_store.update(**{key: parsed})
            print(f"Updated {key} = {parsed}")
            return 0
    if args.command == "plugins":
        if args.action == "list":
            for d in (Path("plugins"), Path("examples/plugins")):
                if d.exists():
                    await pm.discover_and_load(d)
            plugins = pm.list_plugins()
            if not plugins:
                print("No plugins discovered.")
            for p in plugins:
                name = p["manifest"].name if p["manifest"] else "Unknown"
                print(f"ID: {p['id']} | Status: {p['status']} | Name: {name}")
            return 0
        if args.action == "validate":
            print("Use: plugins list")
            return 0
        if args.action == "ui":
            host = args.host or config.ui.host
            port = args.port or config.ui.port
            config.ui.host = host
            config.ui.port = port
            ui_dir = Path("examples/plugins/web_ui_plugin")
            if not ui_dir.exists():
                print("Web UI plugin not found", file=sys.stderr)
                return 1
            await pm.discover_and_load(ui_dir.parent)
            print(f"Web UI: http://{host}:{port}")
            print("Press Ctrl+C to stop.")
            try:
                while True:
                    await asyncio.sleep(3600)
            except (KeyboardInterrupt, asyncio.CancelledError):
                await pm.shutdown_all()
            return 0
    if args.command == "sessions":
        if args.action == "list":
            sessions = await sm.list_sessions()
            if not sessions:
                print("No sessions found.")
            for s in sessions:
                print(f"ID: {s['session_id']} | Goal: {s['goal']} | Status: {s['status']}")
            return 0
        if args.action == "show":
            session = await sm.get_session(UUID(args.id))
            if session:
                print(session)
            else:
                print(f"Session {args.id} not found.")
                return 1
            return 0
    if args.command == "settings":
        from agent_platform.settings.ui_store import UiSettingsStore, RESPONSE_LANGUAGES
        ui_store = UiSettingsStore()
        if args.action == "languages":
            for code, name in RESPONSE_LANGUAGES.items():
                print(f"  {code:8} {name}")
            return 0
        if args.action == "language":
            ui = ui_store.load()
            if not args.value:
                code = getattr(ui.chat, "response_language", "auto")
                print(f"{code} — {RESPONSE_LANGUAGES.get(code, code)}")
                return 0
            raw = args.value.strip()
            code = None
            low = raw.lower()
            if raw in RESPONSE_LANGUAGES:
                code = raw
            else:
                for k, v in RESPONSE_LANGUAGES.items():
                    if v.lower() == low or k.lower() == low:
                        code = k
                        break
            if not code:
                print(f"Unknown language: {raw}. Use: settings languages")
                return 1
            ui.chat.response_language = code
            ui_store.save(ui)
            print(f"Response language set to {code} — {RESPONSE_LANGUAGES[code]}")
            return 0

        from agent_platform.settings.component_store import ComponentSettingsStore
        store = ComponentSettingsStore(config.storage.state_dir)
        if args.action == "reset":
            n = store.reset_all()
            # also reset ui_settings.json optional fields? keep ui store
            print(f"Reset {n} component setting file(s) under {config.storage.state_dir}")
            return 0
        if args.action == "show":
            for kind, d in (("tools", store.tools_dir), ("plugins", store.plugins_dir)):
                print(f"[{kind}] {d}")
                for f in sorted(d.glob("*.json")):
                    print(f"  {f.name}")
            return 0
        print("Usage: settings reset | settings show")
        return 1
    if args.command == "mcp":
        if args.action == "validate":
            print(f"MCP enabled: {config.mcp.enabled}")
            return 0
        if args.action == "serve":
            print("Requires: pip install agent_platform[mcp]")
            return 1

    parser.print_help()
    return 0


def main(argv: Optional[list] = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
