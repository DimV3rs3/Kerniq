"""Startup helpers: dependency check/install and environment readiness."""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# (import_name, pip_name)
CORE_DEPS: List[Tuple[str, str]] = [
    ("httpx", "httpx"),
    ("pydantic", "pydantic"),
]

OPTIONAL_DEPS: List[Tuple[str, str]] = [
    ("mcp", "mcp"),
]


@dataclass
class DepStatus:
    name: str
    import_name: str
    available: bool
    error: Optional[str] = None


@dataclass
class BootstrapReport:
    checked: List[DepStatus] = field(default_factory=list)
    installed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    python: str = ""

    @property
    def ok(self) -> bool:
        return not self.failed and all(d.available for d in self.checked if d.name in {c[1] for c in CORE_DEPS})


def check_dependency(import_name: str, pip_name: str) -> DepStatus:
    try:
        importlib.import_module(import_name)
        return DepStatus(name=pip_name, import_name=import_name, available=True)
    except ImportError as e:
        return DepStatus(
            name=pip_name, import_name=import_name, available=False, error=str(e)
        )


def install_package(pip_name: str) -> bool:
    """Attempt to install a package with the current interpreter."""
    cmd = [sys.executable, "-m", "pip", "install", pip_name]
    logger.info("Installing dependency: %s", pip_name)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0:
            logger.info("Installed %s", pip_name)
            return True
        logger.error("Failed to install %s: %s", pip_name, result.stderr[-500:])
        return False
    except Exception as e:
        logger.error("Install error for %s: %s", pip_name, e)
        return False


def ensure_dependencies(
    *,
    auto_install: bool = True,
    include_optional: bool = False,
    extra: Optional[Sequence[Tuple[str, str]]] = None,
) -> BootstrapReport:
    """
    Check required packages; optionally install missing ones.

    Safe defaults: only core deps are required. Optional (mcp) only if requested.
    """
    report = BootstrapReport(python=sys.version)
    deps = list(CORE_DEPS)
    if include_optional:
        deps.extend(OPTIONAL_DEPS)
    if extra:
        deps.extend(list(extra))

    for import_name, pip_name in deps:
        status = check_dependency(import_name, pip_name)
        if not status.available and auto_install:
            if install_package(pip_name):
                # Re-check
                status = check_dependency(import_name, pip_name)
                if status.available:
                    report.installed.append(pip_name)
                else:
                    report.failed.append(pip_name)
            else:
                report.failed.append(pip_name)
        elif not status.available:
            report.failed.append(pip_name)
        report.checked.append(status)

    return report


def format_bootstrap_report(report: BootstrapReport) -> str:
    lines = [f"Python: {report.python.split()[0]}"]
    for d in report.checked:
        mark = "OK" if d.available else "MISSING"
        lines.append(f"  {d.name}: {mark}")
    if report.installed:
        lines.append("Installed: " + ", ".join(report.installed))
    if report.failed:
        lines.append("Failed: " + ", ".join(report.failed))
    return "\n".join(lines)
