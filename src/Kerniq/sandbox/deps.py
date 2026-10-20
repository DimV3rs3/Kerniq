"""Find required packages from project files and install only the missing ones."""

from __future__ import annotations

import ast
import logging
import os
import re
from Kerniq.sandbox.proc import hidden_run
import sys
import tomllib
from pathlib import Path

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".kerniq-venv",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".kerniq",
}
SKIP_TOP = {
    "kerniq",
    "pip",
    "setuptools",
    "wheel",
    "pkg-resources",
    "pkg_resources",
    "__future__",
}
IMPORT_TO_PIP = {
    "cv2": "opencv-python",
    "pil": "pillow",
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "attr": "attrs",
    "dateutil": "python-dateutil",
    "gi": "pygobject",
    "serial": "pyserial",
    "usb": "pyusb",
    "crypto": "pycryptodome",
    "skimage": "scikit-image",
    "wx": "wxpython",
}
_NAME = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)")
_MAX_PY = 500


def auto_deps_enabled() -> bool:
    if os.environ.get("KERNIQ_NO_AUTO_DEPS") == "1":
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


def normalize_name(spec: str) -> str:
    text = (spec or "").strip().replace(" ", "")
    match = _NAME.match(text)
    if not match:
        return ""
    return match.group(1).lower().replace("_", "-")


def split_spec(spec: str) -> tuple[str, str] | None:
    text = (spec or "").strip()
    if not text or text.startswith(("-", "#", ".")):
        return None
    name = normalize_name(text)
    if not name or name in SKIP_TOP:
        return None
    return name, text


def _stdlib_names() -> set[str]:
    names = set(getattr(sys, "stdlib_module_names", ()))
    names.update(sys.builtin_module_names)
    return {n.lower() for n in names}


def _add(found: dict[str, str], spec: str, *, pinned: bool) -> None:
    parsed = split_spec(spec)
    if parsed is None:
        return
    name, text = parsed
    current = found.get(name)
    if current is None:
        found[name] = text
        return
    current_pinned = current != name and any(op in current for op in ("==", ">=", "<=", "~=", "!=", ">", "<"))
    new_pinned = pinned or (text != name and any(op in text for op in ("==", ">=", "<=", "~=", "!=", ">", "<")))
    if new_pinned and not current_pinned:
        found[name] = text


def imports_in_source(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = (alias.name or "").split(".", 1)[0]
                if top:
                    names.append(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            top = (node.module or "").split(".", 1)[0]
            if top:
                names.append(top)
    return names


def _mapped(import_name: str) -> str:
    key = import_name.lower()
    return IMPORT_TO_PIP.get(key, import_name)


def scan_tree(root: Path) -> list[str]:
    """Requirement specs for a plugin, tool pack, or workspace. Pinned specs win over bare imports."""
    root = Path(root)
    if not root.is_dir():
        return []
    found: dict[str, str] = {}
    stdlib = _stdlib_names()
    for path in _requirement_files(root):
        _read_requirement_file(path, found)
    py_seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            py_seen += 1
            if py_seen > _MAX_PY:
                break
            file_path = Path(dirpath) / filename
            try:
                source = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for imported in imports_in_source(source):
                if imported.lower() in stdlib:
                    continue
                _add(found, _mapped(imported), pinned=False)
        if py_seen > _MAX_PY:
            break
    return [found[key] for key in sorted(found)]


def _requirement_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")]
        for filename in filenames:
            lowered = filename.lower()
            if lowered == "pyproject.toml" or lowered == "manifest.toml" or (
                lowered.startswith("requirements") and lowered.endswith(".txt")
            ):
                files.append(Path(dirpath) / filename)
    return files


def _read_requirement_file(path: Path, found: dict[str, str]) -> None:
    try:
        if path.suffix == ".toml":
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        else:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                _add(found, line.split("#", 1)[0].strip(), pinned=True)
            return
    except (OSError, tomllib.TOMLDecodeError):
        return
    if path.name == "pyproject.toml":
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict):
            for dep in project.get("dependencies") or []:
                if isinstance(dep, str):
                    _add(found, dep, pinned=True)
        return
    deps = []
    if isinstance(data, dict):
        raw = data.get("dependencies")
        if raw is None and isinstance(data.get("plugin"), dict):
            raw = data["plugin"].get("dependencies")
        if isinstance(raw, list):
            deps = raw
    for dep in deps:
        if isinstance(dep, str):
            _add(found, dep, pinned=True)


def installed_names(python: str) -> set[str]:
    result = hidden_run(
        [python, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    names: set[str] = set()
    if result.returncode != 0:
        return names
    for line in result.stdout.splitlines():
        parsed = split_spec(line.split(" @ ", 1)[0])
        if parsed:
            names.add(parsed[0])
    return names


def missing_specs(specs: list[str], present: set[str]) -> list[str]:
    missing: list[str] = []
    seen: set[str] = set()
    for spec in specs:
        parsed = split_spec(spec)
        if parsed is None:
            continue
        name, text = parsed
        if name in present or name in seen or name.startswith("plugin-"):
            continue
        seen.add(name)
        missing.append(text)
    return missing


def install_specs(python: str, specs: list[str]) -> list[str]:
    if not specs:
        return []
    if _pip_install(python, specs):
        return list(specs)
    installed: list[str] = []
    for spec in specs:
        if _pip_install(python, [spec]):
            installed.append(spec)
        else:
            logger.warning("Could not install %s for %s", spec, python)
    return installed


def _pip_install(python: str, specs: list[str]) -> bool:
    cmd = [python, "-m", "pip", "install", *specs]
    result = hidden_run(cmd, capture_output=True, text=True, timeout=180, check=False)
    if result.returncode == 0:
        return True
    err = (result.stderr or "") + (result.stdout or "")
    if "externally-managed" in err:
        retry = hidden_run(
            [python, "-m", "pip", "install", "--break-system-packages", *specs],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        return retry.returncode == 0
    return False


def ensure_project_deps(root: Path, python: str | None = None, *, enabled: bool | None = None) -> list[str]:
    """Install packages a plugin, tool pack, or workspace needs. Returns specs that were installed."""
    if enabled is None:
        enabled = auto_deps_enabled()
    if not enabled:
        return []
    interpreter = python or sys.executable
    specs = scan_tree(Path(root))
    if not specs:
        return []
    present = installed_names(interpreter)
    needed = missing_specs(specs, present)
    if not needed:
        return []
    logger.info("Installing %s into %s", ", ".join(needed), interpreter)
    return install_specs(interpreter, needed)


def install_product_tree(root: Path, python: str | None = None) -> list[str]:
    """Scan Kerniq plugins and tool packs and install what they import."""
    root = Path(root)
    interpreter = python or sys.executable
    installed: list[str] = []
    targets = [root / "plugins", root / "src" / "Kerniq" / "tools" / "packs"]
    for base in targets:
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.is_dir():
                installed.extend(ensure_project_deps(child, interpreter, enabled=True))
    return installed
