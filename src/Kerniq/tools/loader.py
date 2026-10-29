"""Discover and load tool packs from ``Kerniq.tools.packs`` and optional user dirs."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Type

from .pack import ToolPack
from .registry import ToolRegistry
from ..interfaces.tools import Tool

logger = logging.getLogger(__name__)


def _load_pack_class(module_name: str) -> Optional[Type[ToolPack]]:
    try:
        mod = importlib.import_module(module_name)
    except Exception as e:
        logger.warning("Failed to import tool pack %s: %s", module_name, e)
        return None
    cls = getattr(mod, "Pack", None) or getattr(mod, "ToolPackImpl", None)
    if cls is None:
        # find first ToolPack subclass
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if isinstance(obj, type) and issubclass(obj, ToolPack) and obj is not ToolPack:
                cls = obj
                break
    if cls is None:
        logger.warning("No ToolPack in %s", module_name)
        return None
    return cls


def discover_pack_classes(extra_dirs: Optional[Sequence[Path]] = None) -> List[Type[ToolPack]]:
    classes: List[Type[ToolPack]] = []
    seen = set()
    try:
        import Kerniq.tools.packs as packs_pkg
    except Exception as exc:
        logger.warning("Cannot import tool packs package: %s", exc)
        packs_pkg = None
    if packs_pkg is not None:
        prefix = packs_pkg.__name__ + "."
        for mod in pkgutil.iter_modules(packs_pkg.__path__, prefix):
            if not mod.ispkg:
                continue
            cls = _load_pack_class(mod.name)
            if cls is None:
                continue
            key = cls.__module__
            if key in seen:
                continue
            seen.add(key)
            classes.append(cls)
    # optional user packs: each subdir with __init__.py defining Pack
    for d in extra_dirs or []:
        d = Path(d)
        if not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_dir() or not (child / "__init__.py").exists():
                continue
            # load via path
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    f"user_tool_pack_{child.name}", child / "__init__.py"
                )
                if not spec or not spec.loader:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                cls = getattr(mod, "Pack", None)
                if cls and isinstance(cls, type) and issubclass(cls, ToolPack):
                    classes.append(cls)
            except Exception as e:
                logger.warning("User tool pack %s failed: %s", child, e)
    return classes


def load_all_tools(
    workspace: str,
    *,
    policy: Any = None,
    extra_pack_dirs: Optional[Sequence[Path]] = None,
    enabled_packs: Optional[Sequence[str]] = None,
) -> List[Tool]:
    """Instantiate tools from all discovered packs."""
    tools: List[Tool] = []
    for cls in discover_pack_classes(extra_pack_dirs):
        try:
            pack: ToolPack = cls()
            if enabled_packs is not None and pack.pack_id not in enabled_packs:
                continue
            kwargs: Dict[str, Any] = {}
            if policy is not None and pack.pack_id in {"terminal", "filesystem"}:
                kwargs["policy"] = policy
            for t in pack.create_tools(workspace, **kwargs):
                # tag pack metadata if missing
                if not getattr(t, "pack_id", None):
                    try:
                        object.__setattr__(t, "pack_id", pack.pack_id)
                    except Exception:
                        pass
                try:
                    t._pack_include_in_plan = bool(getattr(pack, "include_in_plan", False))
                except Exception:
                    pass
                tools.append(t)
        except Exception as e:
            logger.exception("Pack %s failed to create tools: %s", cls, e)
    return tools


def register_builtin_tools(
    registry: ToolRegistry,
    workspace: str,
    *,
    policy: Any = None,
) -> List[Tool]:
    """Register all built-in pack tools into a registry. Returns registered list."""
    registered = []
    for t in load_all_tools(workspace, policy=policy):
        try:
            registry.register_tool(t)
            registered.append(t)
        except ValueError as e:
            logger.warning("Skip tool: %s", e)
    return registered
