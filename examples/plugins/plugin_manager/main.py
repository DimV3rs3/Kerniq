"""Plugin Manager: search GitHub, install, remove, and security-scan plugins."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from Kerniq.plugins.base import Plugin, PluginContext
from Kerniq.plugins.manifest import PluginManifest
from Kerniq.interfaces.tools import Tool, ToolResult

logger = logging.getLogger(__name__)

# Heuristic dangerous patterns in plugin source (not a full sandbox audit)
_DANGEROUS_PATTERNS = [
    (re.compile(r"\beval\s*\("), "use of eval()"),
    (re.compile(r"\bexec\s*\("), "use of exec()"),
    (re.compile(r"__import__\s*\(\s*['\"]os['\"]"), "dynamic import of os"),
    (re.compile(r"subprocess\.(call|run|Popen|check_output)"), "subprocess invocation"),
    (re.compile(r"os\.system\s*\("), "os.system()"),
    (re.compile(r"socket\.socket\s*\("), "raw socket"),
    (re.compile(r"ctypes\."), "ctypes (native code)"),
    (re.compile(r"pickle\.loads?\s*\("), "pickle load"),
    (re.compile(r"requests\.(get|post|put|delete)\s*\([^)]*http://"), "cleartext HTTP request"),
]

_GITHUB_API = "https://api.github.com"
_SEARCH_QUERY_DEFAULT = "kerniq plugin topic:kerniq-plugin"


def _plugins_root() -> Path:
    # Prefer project-local plugins/ next to cwd
    cwd = Path.cwd()
    local = cwd / "plugins"
    if local.is_dir():
        return local.resolve()
    # Fallback: relative to this package
    return (Path(__file__).resolve().parent.parent).resolve()


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)[:80]


class SearchPluginsTool(Tool):
    @property
    def tool_id(self) -> str:
        return "plugin_search_github"

    @property
    def name(self) -> str:
        return "plugin_search"

    @property
    def description(self) -> str:
        return (
            "Search GitHub for Kerniq-compatible plugins. "
            "Query is combined with keywords 'kerniq plugin'. Returns repo name, stars, URL, description."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords (e.g. weather, browser, rag)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-20)",
                    "default": 10,
                },
            },
            "required": ["query"],
        }

    @property
    def category(self) -> str:
        return "plugins"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        query = (arguments.get("query") or "").strip()
        limit = int(arguments.get("limit") or 10)
        limit = max(1, min(limit, 20))
        if not query:
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error="query is required",
                human_readable="query is required",
            )

        q = f"{query} kerniq plugin in:name,description,readme"
        url = str(httpx.URL(
            f"{_GITHUB_API}/search/repositories",
            params={"q": q, "sort": "stars", "order": "desc", "per_page": str(limit)},
        ))
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "Kerniq-PluginManager/1.0"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 403:
                    return ToolResult(
                        tool_call_id=arguments.get("tool_call_id", ""),
                        tool_id=self.tool_id,
                        status="error",
                        success=False,
                        error="GitHub API rate limited",
                        human_readable="GitHub API rate limited. Set GITHUB_TOKEN or retry later.",
                    )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error=str(e),
                human_readable=f"Search failed: {e}",
            )

        items = []
        for repo in data.get("items", [])[:limit]:
            items.append(
                {
                    "full_name": repo.get("full_name"),
                    "description": repo.get("description"),
                    "stars": repo.get("stargazers_count"),
                    "url": repo.get("html_url"),
                    "clone_url": repo.get("clone_url"),
                    "default_branch": repo.get("default_branch", "main"),
                    "updated_at": repo.get("updated_at"),
                }
            )
        lines = [
            f"- {i['full_name']} ★{i['stars']}: {i['description'] or ''} ({i['url']})"
            for i in items
        ]
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="success",
            output={"count": len(items), "repos": items},
            human_readable=f"Found {len(items)} repos:\n" + ("\n".join(lines) if lines else "(none)"),
        )


class InstallPluginTool(Tool):
    @property
    def tool_id(self) -> str:
        return "plugin_install_github"

    @property
    def name(self) -> str:
        return "plugin_install"

    @property
    def description(self) -> str:
        return (
            "Install a plugin from a GitHub repository (owner/repo or full URL). "
            "Downloads zip of default branch into ./plugins/<name>. "
            "Runs a basic security scan before keeping the install."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo": {
                    "type": "string",
                    "description": "GitHub owner/repo or https://github.com/owner/repo",
                },
                "target_name": {
                    "type": "string",
                    "description": "Optional folder name under plugins/",
                },
                "ref": {
                    "type": "string",
                    "description": "Branch/tag/commit (default: repo default branch)",
                },
                "force": {
                    "type": "boolean",
                    "description": "Overwrite existing plugin directory",
                    "default": False,
                },
            },
            "required": ["repo"],
        }

    @property
    def category(self) -> str:
        return "plugins"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        raw = (arguments.get("repo") or "").strip()
        force = bool(arguments.get("force", False))
        ref = (arguments.get("ref") or "").strip() or None
        target_name = (arguments.get("target_name") or "").strip() or None

        m = re.search(r"github\.com[/:]([^/]+)/([^/.]+)", raw)
        if m:
            owner, repo = m.group(1), m.group(2)
        elif "/" in raw and not raw.startswith("http"):
            parts = raw.strip("/").split("/")
            if len(parts) >= 2:
                owner, repo = parts[0], parts[1]
            else:
                return self._err(arguments, "Invalid repo; use owner/repo")
        else:
            return self._err(arguments, "Invalid repo; use owner/repo or GitHub URL")

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Kerniq-PluginManager/1.0",
        }
        # Optional token from env
        import os

        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                if not ref:
                    meta = await client.get(f"{_GITHUB_API}/repos/{owner}/{repo}", headers=headers)
                    if meta.status_code != 200:
                        return self._err(arguments, f"Repo not found: {owner}/{repo} ({meta.status_code})")
                    ref = meta.json().get("default_branch") or "main"

                zip_url = str(httpx.URL(f"{_GITHUB_API}/repos/{owner}/{repo}/zipball/{ref}"))
                resp = await client.get(zip_url, headers=headers)
                if resp.status_code != 200:
                    return self._err(
                        arguments,
                        f"Failed to download {owner}/{repo}@{ref}: HTTP {resp.status_code}",
                    )
                content = resp.content
        except Exception as e:
            return self._err(arguments, f"Download failed: {e}")

        plugins_dir = _plugins_root()
        plugins_dir.mkdir(parents=True, exist_ok=True)
        folder = _safe_name(target_name or repo)
        dest = plugins_dir / folder
        if dest.exists():
            if not force:
                return self._err(
                    arguments,
                    f"Plugin directory already exists: {dest}. Pass force=true to overwrite.",
                )
            shutil.rmtree(dest)

        tmp_zip = plugins_dir / f".{folder}.zip"
        tmp_extract = plugins_dir / f".{folder}.extract"
        try:
            tmp_zip.write_bytes(content)
            if tmp_extract.exists():
                shutil.rmtree(tmp_extract)
            tmp_extract.mkdir()
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(tmp_extract)
            # GitHub zip has a single top-level directory
            children = [c for c in tmp_extract.iterdir() if c.is_dir()]
            if len(children) == 1:
                shutil.move(str(children[0]), str(dest))
            else:
                dest.mkdir(parents=True, exist_ok=True)
                for c in tmp_extract.iterdir():
                    shutil.move(str(c), str(dest / c.name))
        except Exception as e:
            return self._err(arguments, f"Extract failed: {e}")
        finally:
            if tmp_zip.exists():
                tmp_zip.unlink(missing_ok=True)
            if tmp_extract.exists():
                shutil.rmtree(tmp_extract, ignore_errors=True)

        # Prefer nested plugin dir if zip is a monorepo
        if not (dest / "manifest.toml").exists():
            nested = list(dest.rglob("manifest.toml"))
            if nested:
                # move the directory containing manifest to dest
                plugin_root = nested[0].parent
                if plugin_root != dest:
                    staging = plugins_dir / f".{folder}.staging"
                    if staging.exists():
                        shutil.rmtree(staging)
                    shutil.copytree(plugin_root, staging)
                    shutil.rmtree(dest)
                    shutil.move(str(staging), str(dest))

        scan = _security_scan(dest)
        sha = hashlib.sha256(content).hexdigest()[:16]
        if scan["risk"] == "critical":
            shutil.rmtree(dest, ignore_errors=True)
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error="Security scan failed (critical)",
                output={"scan": scan, "sha256_prefix": sha},
                human_readable=(
                    f"Install aborted: critical security findings in {owner}/{repo}.\n"
                    + "\n".join(scan.get("findings", [])[:10])
                ),
            )

        has_manifest = (dest / "manifest.toml").exists()
        msg = (
            f"Installed {owner}/{repo}@{ref} → {dest}\n"
            f"manifest.toml: {'yes' if has_manifest else 'MISSING'}\n"
            f"security risk: {scan['risk']} ({len(scan.get('findings', []))} findings)\n"
            f"content sha256 prefix: {sha}"
        )
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="success",
            output={
                "path": str(dest),
                "repo": f"{owner}/{repo}",
                "ref": ref,
                "has_manifest": has_manifest,
                "scan": scan,
                "sha256_prefix": sha,
            },
            human_readable=msg,
        )

    def _err(self, arguments: Dict[str, Any], msg: str) -> ToolResult:
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="error",
            success=False,
            error=msg,
            human_readable=msg,
        )


class RemovePluginTool(Tool):
    @property
    def tool_id(self) -> str:
        return "plugin_remove"

    @property
    def name(self) -> str:
        return "plugin_remove"

    @property
    def description(self) -> str:
        return (
            "Remove an installed plugin directory under ./plugins/<name>. "
            "Does not uninstall Python packages — only deletes the plugin folder."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Plugin folder name under plugins/",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to actually delete",
                    "default": False,
                },
            },
            "required": ["name"],
        }

    @property
    def category(self) -> str:
        return "plugins"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        name = _safe_name((arguments.get("name") or "").strip())
        confirm = bool(arguments.get("confirm", False))
        if not name:
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error="name required",
                human_readable="name required",
            )
        dest = _plugins_root() / name
        if not dest.exists():
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error=f"Not found: {dest}",
                human_readable=f"Plugin directory not found: {name}",
            )
        if not confirm:
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error="confirm=true required",
                human_readable=f"Refusing to delete {dest} without confirm=true",
            )
        try:
            shutil.rmtree(dest)
        except Exception as e:
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error=str(e),
                human_readable=f"Remove failed: {e}",
            )
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="success",
            output={"removed": str(dest)},
            human_readable=f"Removed plugin directory: {dest}",
        )


class SecurityScanPluginTool(Tool):
    @property
    def tool_id(self) -> str:
        return "plugin_security_scan"

    @property
    def name(self) -> str:
        return "plugin_security_scan"

    @property
    def description(self) -> str:
        return (
            "Run a basic static security scan on a plugin directory under ./plugins/<name>. "
            "Looks for eval/exec, subprocess, os.system, pickle, ctypes, etc. "
            "Not a guarantee of safety — review findings manually."
        )

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Plugin folder name under plugins/",
                },
            },
            "required": ["name"],
        }

    @property
    def category(self) -> str:
        return "plugins"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        name = _safe_name((arguments.get("name") or "").strip())
        dest = _plugins_root() / name
        if not dest.is_dir():
            return ToolResult(
                tool_call_id=arguments.get("tool_call_id", ""),
                tool_id=self.tool_id,
                status="error",
                success=False,
                error=f"Not found: {dest}",
                human_readable=f"Plugin directory not found: {name}",
            )
        scan = _security_scan(dest)
        lines = [f"risk={scan['risk']}", f"files_scanned={scan['files_scanned']}"]
        lines.extend(scan.get("findings", [])[:30])
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="success",
            output=scan,
            human_readable="\n".join(lines),
        )


class ListInstalledPluginsTool(Tool):
    @property
    def tool_id(self) -> str:
        return "plugin_list_installed"

    @property
    def name(self) -> str:
        return "plugin_list_installed"

    @property
    def description(self) -> str:
        return "List installed plugin directories under ./plugins/ with manifest metadata when available."

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    @property
    def category(self) -> str:
        return "plugins"

    async def execute(self, arguments: Dict[str, Any], context: Any) -> ToolResult:
        root = _plugins_root()
        items = []
        if root.is_dir():
            for d in sorted(root.iterdir()):
                if not d.is_dir() or d.name.startswith("."):
                    continue
                entry: Dict[str, Any] = {"folder": d.name, "path": str(d)}
                man = d / "manifest.toml"
                if man.exists():
                    try:
                        import tomllib

                        with open(man, "rb") as f:
                            data = tomllib.load(f)
                        if "plugin" in data and isinstance(data["plugin"], dict):
                            data = {**data["plugin"], **{k: v for k, v in data.items() if k != "plugin"}}
                        entry["plugin_id"] = data.get("plugin_id")
                        entry["name"] = data.get("name")
                        entry["version"] = data.get("version")
                        entry["description"] = data.get("description")
                    except Exception as e:
                        entry["manifest_error"] = str(e)
                else:
                    entry["manifest"] = None
                items.append(entry)
        lines = []
        for i in items:
            lines.append(
                f"- {i['folder']}: {i.get('name') or '?'} "
                f"v{i.get('version') or '?'} ({i.get('plugin_id') or 'no-id'})"
            )
        return ToolResult(
            tool_call_id=arguments.get("tool_call_id", ""),
            tool_id=self.tool_id,
            status="success",
            output={"plugins": items, "root": str(root)},
            human_readable=f"Installed under {root}:\n" + ("\n".join(lines) if lines else "(none)"),
        )


def _security_scan(root: Path) -> Dict[str, Any]:
    findings: List[str] = []
    files_scanned = 0
    risk = "low"
    for py in root.rglob("*.py"):
        if any(p in py.parts for p in (".git", "__pycache__", ".venv", "venv")):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_scanned += 1
        for pattern, label in _DANGEROUS_PATTERNS:
            for m in pattern.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append(f"{py.relative_to(root)}:{line_no}: {label}")
                if label in ("use of eval()", "use of exec()", "pickle load", "ctypes (native code)"):
                    risk = "critical"
                elif risk != "critical":
                    risk = "medium"
    # Manifest checks
    man = root / "manifest.toml"
    if not man.exists():
        findings.append("missing manifest.toml")
        if risk == "low":
            risk = "medium"
    return {
        "risk": risk,
        "files_scanned": files_scanned,
        "findings": findings,
    }


class PluginImpl(Plugin):
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            plugin_id="plugin_plugin_manager",
            name="Plugin Manager",
            version="1.0.0",
            api_version="1.0",
            entry_point="main.PluginImpl",
            description="Search/install/remove/scan plugins from GitHub",
            capabilities=["tools"],
            author="Kerniq",
            license="MIT",
            permissions=["network", "filesystem"],
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    async def initialize(self, context: PluginContext) -> bool:
        for tool in (
            SearchPluginsTool(),
            InstallPluginTool(),
            RemovePluginTool(),
            SecurityScanPluginTool(),
            ListInstalledPluginsTool(),
        ):
            try:
                context.register_tool(tool)
            except ValueError:
                # already registered
                pass
        if context.logger:
            context.logger.info("Plugin Manager initialized (search/install/remove/scan)")
        return True

    async def shutdown(self) -> None:
        pass
