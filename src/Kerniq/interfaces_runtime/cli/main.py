"""AI Agent Platform CLI."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
from uuid import UUID

from Kerniq.bootstrap import ensure_dependencies, format_bootstrap_report
from Kerniq.core.agent import Agent
from Kerniq.models.providers.mock import MockProvider
from Kerniq.models.providers.lm_studio import LMStudioProvider
from Kerniq.models.system_info import collect_system_info, recommend_for_lm_studio
from Kerniq.tools.registry import ToolRegistry
from Kerniq.tools.loader import register_builtin_tools, load_all_tools
from Kerniq.tools.filesystem import FileSystemTools
from Kerniq.tools.terminal import TerminalTools
from Kerniq.tools.web_search import WebSearchTool, FetchUrlTool
from Kerniq.tools.terminal import TerminalTools
from Kerniq.tools.web_search import WebSearchTool, FetchUrlTool
from Kerniq.tools.settings import ToolSettingsStore
from Kerniq.security.policy import SecurityPolicy
from Kerniq.settings.loader import SettingsProvider
from Kerniq.core.verifier import BasicVerifier
from Kerniq.storage.json_store import JsonStorage
from Kerniq.sessions.manager import SessionManager
from Kerniq.plugins.manager import PluginManager
from Kerniq.devtools.paths import find_plugins_dirs, find_project_root
from Kerniq.plugins.base import PluginContext

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def maybe_auto_update(argv: Optional[list] = None) -> Optional[int]:
    """If a newer release exists, apply it and re-exec the same command.

    Skipped for: uninstall/remove/update --help, and when KERNIQ_NO_AUTO_UPDATE=1.
    Settings/state are preserved (no wipe).
    """
    import os
    import sys
    if os.environ.get("KERNIQ_NO_AUTO_UPDATE", "").strip() in ("1", "true", "yes"):
        return None
    if os.environ.get("KERNIQ_UPDATING") == "1":
        return None  # already re-exec after update
    args = list(argv) if argv is not None else sys.argv[1:]
    if not args:
        return None
    skip = {"uninstall", "remove", "update", "--help", "-h", "--version"}
    if args[0] in skip:
        return None
    try:
        import asyncio
        from Kerniq.devtools.update_check import check_for_update, apply_update

        info = asyncio.run(check_for_update())
        if not info.is_newer:
            return None
        print(
            f"Kerniq update available: {info.local_version} → {info.remote_version}. "
            "Updating in place (settings kept)…"
        )
        ok, msg = apply_update()
        print(msg)
        if not ok:
            print("Auto-update failed; continuing with current version.")
            return None
        # Re-exec original command with fresh code
        env = os.environ.copy()
        env["KERNIQ_UPDATING"] = "1"
        os.execvpe(sys.executable, [sys.executable, "-m", "Kerniq", *args], env)
    except Exception as e:
        logger.debug("auto-update skipped: %s", e)
        return None
    return None



def _apply_ui_log_level():
    """Use Web UI plugin log_level when running plugins ui (default: warning)."""
    try:
        from Kerniq.settings.component_store import ComponentSettingsStore
        from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
        store = ComponentSettingsStore()
        # minimal schema for key
        sch = SettingsSchema(
            component_id="plugin_web_ui",
            component_type="plugin",
            title="Web UI",
            fields=[SettingField(key="log_level", label="log", type=SettingType.SELECT, default="warning")],
        )
        vals = store.load("plugin", "plugin_web_ui", sch) or {}
        lvl = str(vals.get("log_level") or "warning").upper()
        level = getattr(logging, lvl, logging.WARNING)
        logging.getLogger().setLevel(level)
        for name in ("httpx", "httpcore", "Kerniq", "plugin", "plugin.web_ui", "cli", "Kerniq.models.providers.lm_studio"):
            logging.getLogger(name).setLevel(level)
    except Exception:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("cli")


def _build_registry(config, workspace: Path, tool_settings_store: ToolSettingsStore):
    ts = tool_settings_store.settings
    registry = ToolRegistry()
    policy = SecurityPolicy(
        workspace_root=workspace,
        disallowed_commands=config.security.disallowed_terminal_commands,
        require_approval_for_high_risk=config.security.require_approval_for_high_risk,
    )
    enabled_packs = []
    if getattr(ts, "fs_enabled", True):
        enabled_packs.append("filesystem")
    if getattr(ts, "terminal_enabled", True):
        enabled_packs.append("terminal")
    if getattr(ts, "web_search_enabled", True) or getattr(ts, "fetch_url_enabled", True):
        enabled_packs.append("web")
    for tool in load_all_tools(str(workspace), policy=policy, enabled_packs=enabled_packs or None):
        # fine-grained enable for web tools
        if tool.name == "web_search" and not getattr(ts, "web_search_enabled", True):
            continue
        if tool.name == "fetch_url" and not getattr(ts, "fetch_url_enabled", True):
            continue
        try:
            registry.register_tool(tool)
        except ValueError:
            pass
        # apply pack-level tool settings when present
        try:
            if tool.name == "web_search" and hasattr(tool, "apply_settings"):
                tool.apply_settings({
                    "max_results": getattr(ts, "web_search_max_results", 5),
                    "timeout": getattr(ts, "web_search_timeout", 15),
                })
            if tool.name == "fetch_url" and hasattr(tool, "apply_settings"):
                tool.apply_settings({"timeout": getattr(ts, "fetch_url_timeout", 20)})
        except Exception:
            pass
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
        from Kerniq.settings.ui_store import UiSettingsStore
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

    mcp_parser = subparsers.add_parser("mcp", help="MCP client/server")
    mcp_sub = mcp_parser.add_subparsers(dest="action")
    mcp_sub.add_parser("validate", help="Check MCP SDK and config")
    mcp_serve = mcp_sub.add_parser("serve", help="Run MCP server on stdio")
    mcp_serve.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Workspace root for tool execution (default: config workspace)",
    )

    update_parser = subparsers.add_parser(
        "update",
        help="Check GitHub for a newer Kerniq release",
    )
    update_parser.add_argument(
        "--repo",
        default="DimV3rs3/Kerniq",
        help="GitHub owner/repo (default: DimV3rs3/Kerniq)",
    )

    un_parser = subparsers.add_parser(
        "uninstall",
        aliases=["remove"],
        help="Uninstall Kerniq from this Python env (pip + console script cleanup)",
    )
    un_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Confirm uninstall without interactive prompt",
    )
    un_parser.add_argument(
        "--purge",
        action="store_true",
        help="Also delete local sessions/logs/state and __pycache__ under project root",
    )
    un_parser.add_argument(
        "--wipe-project",
        action="store_true",
        help="Also permanently delete the Kerniq project source tree(s) from disk",
    )
    un_parser.add_argument(
        "--deferred",
        action="store_true",
        help=argparse.SUPPRESS,  # internal: spawned after kerniq.exe exits
    )

    args = parser.parse_args(argv)

    if args.version or args.command is None:
        from Kerniq import __version__
        if args.version:
            print(__version__)
            return 0
        parser.print_help()
        return 0

    if args.command in ("uninstall", "remove"):
        from Kerniq.devtools.uninstall import uninstall as do_uninstall
        return do_uninstall(
            purge=bool(getattr(args, "purge", False)),
            wipe_project=bool(getattr(args, "wipe_project", False)),
            yes=bool(getattr(args, "yes", False)),
            deferred=bool(getattr(args, "deferred", False)),
        )

    # Soft auto-update (skip uninstall/update itself)
    maybe_auto_update(argv)

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

    if args.command == "update":
        from Kerniq.devtools.update_check import check_for_update

        info = await check_for_update(repo=getattr(args, "repo", None) or "DimV3rs3/Kerniq")
        print(info.message)
        if info.release_url and info.is_newer:
            print(f"Release page: {info.release_url}")
            print("Install/update (from a clone):")
            print("  git pull")
            print('  python -m pip install -e ".[dev,mcp]"')
        # exit 0 if up to date or no remote; 2 if newer available; 1 on auth/network hard fail
        if info.error in ("auth",) and info.remote_version is None:
            return 1
        return 2 if info.is_newer else 0

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
        plugin_dirs = find_plugins_dirs()
        if args.action == "list":
            for d in plugin_dirs:
                await pm.discover_and_load(d)
            plugins = pm.list_plugins()
            if not plugins:
                print("No plugins discovered.")
                if plugin_dirs:
                    print("Searched:", ", ".join(str(d) for d in plugin_dirs))
                else:
                    print("Hint: run from the Kerniq repo, or set KERNIQ_ROOT to the project folder.")
            for p in plugins:
                name = p["manifest"].name if p["manifest"] else "Unknown"
                print(f"ID: {p['id']} | Status: {p['status']} | Name: {name}")
            return 0
        if args.action == "validate":
            print("Use: plugins list")
            return 0
        if args.action == "ui":
            _apply_ui_log_level()
            host = args.host or getattr(config.ui, "host", "127.0.0.1")
            port = int(args.port or getattr(config.ui, "port", 8765))
            config.ui.host = host
            config.ui.port = port
            ui_dir = None
            for d in plugin_dirs:
                cand = d / "web_ui"
                if cand.is_dir() and (cand / "manifest.toml").exists():
                    ui_dir = cand
                    break
            if ui_dir is None:
                print(
                    "Web UI plugin not found. Searched plugin dirs:\n  "
                    + "\n  ".join(str(d) for d in plugin_dirs)
                    + "\nSet KERNIQ_ROOT to the Kerniq project folder.",
                    file=sys.stderr,
                )
                return 1
            for d in plugin_dirs:
                await pm.discover_and_load(d)
            # Report load status
            plugins = {p["id"]: p for p in pm.list_plugins()}
            web = plugins.get("plugin_web_ui") or plugins.get("web_ui")
            if not web or str(web.get("status")) not in (
                "PluginStatus.AVAILABLE",
                "available",
            ):
                # status may be enum
                st = getattr(web, "get", lambda k, d=None: None)("status") if web else None
                st_val = getattr(st, "value", st)
                errs = getattr(pm, "errors", {})
                if st_val != "available":
                    print(
                        f"Web UI plugin failed to start (status={st_val}). "
                        f"errors={errs}",
                        file=sys.stderr,
                    )
                    # still continue if server thread might have started
            # Give server thread a moment
            await asyncio.sleep(0.3)
            display = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
            if host in ("0.0.0.0", "::"):
                try:
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    lan = s.getsockname()[0]
                    s.close()
                except Exception:
                    lan = "127.0.0.1"
                print(f"Web UI (LAN): http://{lan}:{port}")
                print(f"Web UI (local): http://127.0.0.1:{port}")
            else:
                print(f"Web UI: http://{display}:{port}")
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
        from Kerniq.settings.ui_store import UiSettingsStore, RESPONSE_LANGUAGES
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

        from Kerniq.settings.component_store import ComponentSettingsStore
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
            try:
                import mcp  # noqa: F401
                mcp_ok = True
            except ImportError:
                mcp_ok = False
            print(f"MCP enabled in config: {config.mcp.enabled}")
            print(f"MCP SDK installed: {mcp_ok}")
            print(f"published_tools: {config.mcp.published_tools or '(none)'}")
            if config.mcp.servers:
                print(f"configured servers: {len(config.mcp.servers)}")
            if not mcp_ok:
                print("Install: pip install 'Kerniq[mcp]'  or  pip install mcp", file=sys.stderr)
                return 1
            return 0
        if args.action == "serve":
            try:
                import mcp  # noqa: F401
            except ImportError:
                print(
                    "MCP SDK missing. Install with:\n"
                    "  pip install 'Kerniq[mcp]'\n"
                    "  or: pip install mcp",
                    file=sys.stderr,
                )
                return 1
            # Prefer project root so relative config/workspace resolve when LMS spawns us
            root = find_project_root()
            if root:
                try:
                    import os
                    os.chdir(root)
                except Exception:
                    pass
            workspace_path = Path(
                getattr(args, "workspace", None) or str(config.application.workspace_root)
            )
            if not workspace_path.is_absolute() and root:
                workspace_path = (root / workspace_path).resolve()
            else:
                workspace_path = workspace_path.resolve()
            workspace_path.mkdir(parents=True, exist_ok=True)
            store = ToolSettingsStore(config.storage.state_dir)
            registry, _policy = _build_registry(config, workspace_path, store)
            published = list(config.mcp.published_tools or [])
            if not published:
                published = [
                    "list_directory",
                    "read_file",
                    "file_exists",
                    "get_file_info",
                    "web_search",
                    "fetch_url",
                ]
                logger.warning(
                    "mcp.published_tools empty — using safe defaults: %s",
                    published,
                )
            adapter = MCPServerAdapter(
                tool_registry=registry,
                allowed_tools=published,
                workspace=workspace_path,
            )
            # Diagnostics on stderr only (stdio is the MCP protocol stream)
            import sys as _sys
            print(
                f"Starting MCP server (stdio). Published: {published}\n"
                f"workspace={workspace_path}\n"
                f"python={_sys.executable}\n"
                f"cwd={Path.cwd()}",
                file=_sys.stderr,
            )
            print("Connect an MCP client to this process stdin/stdout.", file=_sys.stderr)
            await adapter.run_stdio()
            return 0
        print("Usage: mcp validate | mcp serve [--workspace PATH]")
        return 1

    parser.print_help()
    return 0


def main(argv: Optional[list] = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
