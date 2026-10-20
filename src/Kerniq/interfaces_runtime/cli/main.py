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
from Kerniq.models.factory import build_provider
from Kerniq.models.catalog import provider_ids
from Kerniq.models.providers.lm_studio import LMStudioProvider
from Kerniq.models.system_info import collect_system_info, recommend_for_lm_studio
from Kerniq.tools.registry import ToolRegistry
from Kerniq.tools.settings import ToolSettingsStore
from Kerniq.assembly import build_tool_registry
from Kerniq.settings.loader import SettingsProvider
from Kerniq.core.verifier import BasicVerifier
from Kerniq.storage.json_store import JsonStorage
from Kerniq.persistence.manager import SessionManager
from Kerniq.mcp.server import MCPServerAdapter
from Kerniq.plugins.manager import PluginManager
from Kerniq.devtools.paths import anchored_dir, find_plugins_dirs, find_project_root
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



def _plugin_list_flags(config, plugin_id: str) -> dict:
    try:
        from Kerniq.settings.component_store import ComponentSettingsStore

        store = ComponentSettingsStore(config.storage.state_dir)
        data = store.load("plugin", plugin_id)
        if not isinstance(data, dict):
            return {"enabled": True, "listed": True}
        return {
            "enabled": data.get("enabled", True) is not False,
            "listed": data.get("listed", True) is not False,
        }
    except Exception:
        return {"enabled": True, "listed": True}


def _apply_ui_log_level():
    """Use Web UI plugin log_level when running plugins ui (default: warning)."""
    try:
        from Kerniq.settings.component_store import ComponentSettingsStore
        from Kerniq.settings.loader import SettingsProvider
        from Kerniq.interfaces.settings_schema import SettingsSchema, SettingField, SettingType
        store = ComponentSettingsStore(SettingsProvider().config.storage.state_dir)
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
    del tool_settings_store
    return build_tool_registry(
        workspace,
        config=config,
        state_dir=config.storage.state_dir,
        auto_approve_up_to=getattr(config.security, "auto_approve_up_to", "low"),
    )


async def run_agent(args: argparse.Namespace, config) -> int:
    from Kerniq.core.runtime_flow import (
        act_followup_task,
        apply_runtime,
        attach_compactor,
        handoff_archive,
        plan_research_record,
        open_plan_items,
        probe_context_limit,
        route_mode,
        strip_draft,
        system_prompt_from_settings,
        use_model_for_mode,
    )
    from Kerniq.settings.ui_store import UiSettingsStore

    ui = UiSettingsStore(config.storage.state_dir).load()
    workspace_path = Path(args.workspace or ui.agent.workspace or str(config.application.workspace_root))
    workspace_path.mkdir(parents=True, exist_ok=True)
    ceiling = getattr(ui.chat, "auto_approve_up_to", None) or getattr(
        config.security, "auto_approve_up_to", "low"
    )
    registry, policy = build_tool_registry(
        workspace_path,
        config=config,
        state_dir=config.storage.state_dir,
        auto_approve_up_to=ceiling,
    )

    provider_name = args.provider or ui.api.provider or config.models.default_provider
    timeout = float(ui.agent.timeout_seconds or getattr(config.runtime, "timeout_seconds", None) or 600)
    try:
        provider = build_provider(
            provider_name,
            api=ui.api,
            config=config,
            timeout=timeout,
        )
    except Exception as exc:
        logger.error("Cannot build provider %s: %s", provider_name, exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if provider_name not in ("mock", "mock_provider"):
        if not await provider.check_connection():
            if provider_name == "lm_studio" and not args.provider and ui.api.provider == "lm_studio":
                logger.warning("LM Studio not reachable — falling back to mock")
                from Kerniq.models.providers.mock import MockProvider
                provider = MockProvider()
                provider_name = "mock"
            else:
                print(
                    f"ERROR: provider '{provider_name}' is not reachable. "
                    "Check the key, URL, or CLI path.",
                    file=sys.stderr,
                )
                return 1

    agent = Agent(provider, registry)
    agent.orchestrator.security_policy = policy
    agent.orchestrator.verifier = BasicVerifier(check_files=list(getattr(args, "expect_file", None) or []))
    agent.orchestrator.provider_retries = int(config.runtime.retry_limit or 0)
    apply_runtime(agent.orchestrator, ui)
    await attach_compactor(agent.orchestrator, config)
    agent.orchestrator.context_limit = await probe_context_limit(provider, ui.api.model)
    from Kerniq.interfaces.approvals import ConsoleApprovalProvider
    agent.orchestrator.approval_provider = ConsoleApprovalProvider()

    storage = JsonStorage(anchored_dir(config.storage.sessions_dir))
    sessions = SessionManager(storage)

    def _checkpoint(ctx):
        transcript = (ctx.metadata or {}).get("transcript") or [
            m.model_dump(mode="json") for m in ctx.messages
        ]
        sessions.save_task_sync(
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            goal=ctx.goal,
            status=str((ctx.metadata or {}).get("outcome") or "running"),
            result="",
            workspace=str(workspace_path),
            messages=transcript,
            metadata={"provider": provider_name, "outcome": (ctx.metadata or {}).get("outcome")},
        )

    agent.orchestrator.on_progress = _checkpoint
    system = system_prompt_from_settings(ui, [t.name for t in registry.list_tools()])
    lang = ui.chat.response_language or "auto"
    mode = str(ui.chat.agent_mode or "act").lower()
    if mode not in ("plan", "act"):
        mode = "act"
    if ui.chat.mode_auto:
        mode = await route_mode(provider, args.task, compose_plan=bool(ui.chat.compose_plan))
    auto_act = bool(ui.chat.auto_act_after_plan)
    switched = await use_model_for_mode(provider, ui.api, mode)
    if switched:
        print(f"Could not load the {mode} model: {switched}", file=sys.stderr)
    print(f"Provider: {provider_name} | Model: {getattr(provider, 'model', None) or ui.api.model or '(auto)'} | Workspace: {workspace_path}")
    print(f"Mode: {mode} | Tools: {[t.name for t in registry.list_tools()]}")
    result = await agent.run(
        args.task,
        workspace=str(workspace_path),
        system_prompt=system,
        response_language=lang,
        agent_mode=mode,
        plan_handoff=bool(mode == "plan" and auto_act),
    )
    outcome = ""
    if agent.last_context is not None:
        outcome = str((agent.last_context.metadata or {}).get("outcome") or "")
    failed = outcome in {
        "provider_error", "verification_failed", "tool_loop", "content_loop",
        "empty_response", "max_iterations",
    }
    if mode == "plan" and auto_act and not failed and not open_plan_items(agent.last_context):
        print("Plan finished. Starting Act with a fresh iteration budget.")
        switched = await use_model_for_mode(provider, ui.api, "act")
        if switched:
            print(f"Could not load the act model: {switched}", file=sys.stderr)
        draft = plan_research_record(
            agent.last_context.messages if agent.last_context is not None else [],
            result if isinstance(result, str) else "",
        )
        research = handoff_archive(agent.last_context)
        result = await agent.run(
            act_followup_task(args.task, draft, max_iterations=agent.orchestrator.max_iterations),
            workspace=str(workspace_path),
            system_prompt=system,
            response_language=lang,
            agent_mode="act",
            plan_archive=research or None,
        )
        if agent.last_context is not None:
            outcome = str((agent.last_context.metadata or {}).get("outcome") or "")
    elif mode == "plan" and not auto_act and isinstance(result, str):
        result = strip_draft(result)
    ctx = agent.last_context
    if ctx is not None:
        transcript = (ctx.metadata or {}).get("transcript") or [
            m.model_dump(mode="json") for m in ctx.messages
        ]
        await sessions.save_task(
            session_id=ctx.session_id,
            task_id=ctx.task_id,
            goal=ctx.goal,
            status=str((ctx.metadata or {}).get("outcome") or "unknown"),
            result=result,
            workspace=str(workspace_path),
            messages=transcript,
            metadata={
                "outcome": (ctx.metadata or {}).get("outcome"),
                "provider": provider_name,
            },
        )
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
    run_parser.add_argument("--provider", type=str, help="Provider id (kerniq models list)")

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
    settings_sub.add_parser("show", help="Show the shared settings file")
    settings_set = settings_sub.add_parser(
        "set",
        help="Set one shared setting: settings set agent.max_iterations 20",
    )
    settings_set.add_argument("key", help="section.name, for example api.model or chat.mode_auto")
    settings_set.add_argument("value", help="Use null to clear an optional number such as api.max_tokens")
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
    mcp_sub.add_parser(
        "install",
        help="Write a portable MCP client config for this machine (and LM Studio if present)",
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

    ui_launch = args.command == "plugins" and getattr(args, "action", None) == "ui"
    if config.application.auto_install_deps and args.command in ("run", "doctor", "plugins") and not ui_launch:
        ensure_dependencies(auto_install=True)

    if not (args.command == "mcp" and getattr(args, "action", None) == "serve"):
        try:
            from Kerniq.mcp.launch import write_local_mcp_config

            write_local_mcp_config(
                Path(config.application.workspace_root),
                anchored_dir(config.storage.state_dir),
            )
        except Exception as exc:
            logger.debug("mcp config not written: %s", exc)

    storage = JsonStorage(anchored_dir(config.storage.sessions_dir))
    sm = SessionManager(storage)
    tool_store = ToolSettingsStore(anchored_dir(config.storage.state_dir))

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
            print("Providers:")
            for pid in provider_ids():
                mark = " (default)" if pid == config.models.default_provider else ""
                print(f"  - {pid}{mark}")
            print("Tools are loaded from discovered packs, not a hardcoded list in the CLI.")
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
                phrase = getattr(t, "display_phrase", "") or "calls"
                print(f"  {t.name:22} {phrase}")
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
                return 0
            shown = 0
            for p in plugins:
                name = p["manifest"].name if p["manifest"] else "Unknown"
                flags = _plugin_list_flags(config, p["id"])
                if flags.get("listed") is False:
                    continue
                shown += 1
                state = "on" if flags.get("enabled", True) else "off"
                status = p["status"]
                status_bit = "" if str(status) in ("available", "PluginStatus.AVAILABLE") else f" | {status}"
                err = p.get("error")
                err_bit = f" | {err}" if err else ""
                print(f"ID: {p['id']} | {state}{status_bit}{err_bit} | {name}")
            if not shown:
                print("No plugins to list. Hidden plugins stay out of this list until Show in plugin list is on.")
            return 0
        if args.action == "validate":
            from Kerniq.settings.file import settings_path

            for d in plugin_dirs:
                await pm.discover_and_load(d)
            path = settings_path(config.storage.state_dir)
            print(f"Validated {len(pm.manifests)} plugin(s).")
            print(f"Settings: {path}")
            if pm.errors:
                for pid, err in pm.errors.items():
                    print(f"  {pid}: {err}")
                return 1
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
        from Kerniq.settings.file import read_state_file, settings_path

        state_dir = anchored_dir(config.storage.state_dir)
        ui_store = UiSettingsStore(state_dir)
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
        store = ComponentSettingsStore(state_dir)
        if args.action == "reset":
            n = store.reset_all()
            print(f"Cleared {n} tool/plugin block(s).")
            print("Main settings stay in settings.json. Tool and plugin values stay in tools.json and plugins.json.")
            print("Defaults are written again the next time those components are validated.")
            return 0
        if args.action == "show":
            from Kerniq.settings.file import PLUGINS_FILE, TOOLS_FILE, state_file

            ui = ui_store.load()
            print(f"Main: {settings_path(state_dir)}")
            data = ui.model_dump()
            for section, values in data.items():
                print(f"  [{section}]")
                if isinstance(values, dict):
                    for key, value in values.items():
                        if key in ("api_token",) and value:
                            value = "***"
                        print(f"    {key} = {value}")
            for label, filename, kind in (
                ("Tools", TOOLS_FILE, "tool"),
                ("Plugins", PLUGINS_FILE, "plugin"),
            ):
                print(f"{label}: {state_file(state_dir, filename)}")
                raw_part = read_state_file(state_dir, filename)
                names = raw_part.get("components") if isinstance(raw_part.get("components"), dict) else {}
                if not names:
                    print("    (none yet — run plugins validate or open settings)")
                for name in sorted(names):
                    print(f"    {name}")
            return 0
        if args.action == "set":
            section, _, name = str(args.key).partition(".")
            if not section or not name:
                print("Use section.name, for example: settings set api.temperature 0.4")
                return 1
            raw = str(args.value)
            low = raw.strip().lower()
            if low in ("null", "none"):
                parsed: object = None
            elif low in ("true", "yes", "on"):
                parsed = True
            elif low in ("false", "no", "off"):
                parsed = False
            else:
                try:
                    parsed = int(raw)
                except ValueError:
                    try:
                        parsed = float(raw)
                    except ValueError:
                        parsed = raw
            current = ui_store.load()
            if not hasattr(current, section):
                print(f"Unknown section: {section}")
                return 1
            block = getattr(current, section)
            if not hasattr(block, name):
                print(f"Unknown setting: {section}.{name}")
                return 1
            try:
                setattr(block, name, parsed)
                current = type(current).model_validate(current.model_dump())
            except Exception as exc:
                print(f"Rejected {section}.{name} = {parsed}: {exc}")
                return 1
            ui_store.save(current)
            print(f"{section}.{name} = {getattr(getattr(current, section), name)}")
            return 0
        print("Usage: settings show | settings set section.name value | settings reset | settings language")
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
            registry, policy = _build_registry(config, workspace_path, store)
            from Kerniq.mcp.publish import resolve_published_names

            published = resolve_published_names(registry, policy, config.mcp.published_tools)
            adapter = MCPServerAdapter(
                tool_registry=registry,
                allowed_tools=published,
                workspace=workspace_path,
                security_policy=policy,
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
        if args.action == "install":
            from Kerniq.mcp.launch import install_lmstudio_mcp, write_local_mcp_config

            workspace_path = Path(config.application.workspace_root).resolve()
            local = write_local_mcp_config(workspace_path, Path(config.storage.state_dir))
            print(f"Wrote portable MCP config: {local}")
            ok, msg = install_lmstudio_mcp(workspace_path)
            print(msg if ok else f"LM Studio not updated ({msg}). Point a client at {local}.")
            return 0
        print("Usage: mcp validate | mcp serve [--workspace PATH] | mcp install")
        return 1

    parser.print_help()
    return 0


def main(argv: Optional[list] = None) -> int:
    return asyncio.run(async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
