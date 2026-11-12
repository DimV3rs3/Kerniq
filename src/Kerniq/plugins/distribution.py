"""Install, identify, and update plugins that are not part of the default kit.

The default kit is what ships in this tree. Every other plugin is a folder
with its own manifest. Kerniq does not import it by name. A folder is loaded
only after it has been installed under ``plugins/``.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from Kerniq.devtools.update_check import is_newer

ORIGIN_NAME = ".kerniq-origin.json"
KIT_IDS = frozenset({
    "plugin_plugin_manager",
    "plugin_web_ui",
    "plugin_context_compact",
    "plugin_git_session",
    "plugin_lang_sandbox",
    "plugin_skill_manager",
})
# Canonical repositories. One probe asks for all of them. A plugin does not
# name the others; this map lives in Kerniq.
OFFICIAL_REPOS = {
    "plugin_web_ui": "DimV3rs3/Kerniq-web-ui",
    "plugin_context_compact": "DimV3rs3/Kerniq-context-compact",
    "plugin_plugin_manager": "DimV3rs3/Kerniq-plugin-manager",
    "plugin_skill_manager": "DimV3rs3/Kerniq-skill-manager",
    "plugin_git_session": "DimV3rs3/Kerniq-git-session",
    "plugin_lang_sandbox": "DimV3rs3/Kerniq-language-sandbox",
    "model-advisor": "DimV3rs3/Kerniq-model-advisor",
    "office": "DimV3rs3/Kerniq-office",
    "llm-benchmark": "DimV3rs3/Kerniq-llm-benchmark",
}
_GITHUB_API = "https://api.github.com"
_DANGEROUS = [
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
_CRITICAL = {"use of eval()", "use of exec()", "pickle load"}


def plugins_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    cwd = Path.cwd()
    local = cwd / "plugins"
    if local.is_dir():
        return local.resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "plugins"
        if (cand / "plugin_manager" / "manifest.toml").is_file() or (cand / "web_ui" / "manifest.toml").is_file():
            return cand.resolve()
    return local.resolve()


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Kerniq-PluginManager/1.0"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_github_repo(raw: str) -> tuple[str, str] | None:
    text = (raw or "").strip()
    match = re.search(r"github\.com[/:]([^/\s]+)/([^/\s.]+)", text)
    if match:
        return match.group(1), match.group(2).removesuffix(".git")
    if "/" in text and not text.startswith("http"):
        parts = [part for part in text.strip("/").split("/") if part]
        if len(parts) >= 2 and " " not in parts[0] and " " not in parts[1]:
            return parts[0], parts[1].removesuffix(".git")
    return None


def _manifest_data(path: Path) -> dict[str, Any]:
    with open(path, "rb") as handle:
        raw = tomllib.load(handle)
    if not isinstance(raw, dict):
        return {}
    block = raw.get("plugin")
    if isinstance(block, dict):
        merged = dict(block)
        for key, value in raw.items():
            if key != "plugin" and key not in merged:
                merged[key] = value
        return merged
    return raw


def _class_names(main_py: Path) -> set[str]:
    try:
        tree = ast.parse(main_py.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    return {node.name for node in tree.body if isinstance(node, ast.ClassDef)}


def inspect_plugin(path: str | Path) -> dict[str, Any]:
    """Whether this folder is a complete plugin someone can install on its own."""
    folder = Path(path).resolve()
    errors: list[str] = []
    if not folder.is_dir():
        return {"ok": False, "standalone": False, "kit": False, "errors": ["folder does not exist"], "path": str(folder)}
    manifest_path = folder / "manifest.toml"
    if not manifest_path.is_file():
        errors.append("manifest.toml is missing")
        data: dict[str, Any] = {}
    else:
        try:
            data = _manifest_data(manifest_path)
        except Exception as exc:
            errors.append(f"manifest.toml could not be read: {exc}")
            data = {}
    plugin_id = str(data.get("plugin_id") or "").strip()
    name = str(data.get("name") or plugin_id).strip()
    version = str(data.get("version") or "").strip()
    entry = str(data.get("entry_point") or "").strip()
    if not plugin_id:
        errors.append("plugin_id is missing")
    elif not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,80}", plugin_id):
        errors.append("plugin_id must start with a letter and use only letters, numbers, _ and -")
    if not version or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append("version must look like 1.2.3")
    module_name, _, class_name = entry.partition(".")
    if module_name != "main" or not class_name:
        errors.append("entry_point must look like main.PluginImpl")
    main_py = folder / "main.py"
    if not main_py.is_file():
        errors.append("main.py is missing")
    elif class_name and class_name not in _class_names(main_py):
        errors.append(f"{class_name} is not a class in main.py")
    tools_init = folder / "tools" / "__init__.py"
    if (folder / "tools").is_dir() and tools_init.is_file():
        try:
            source = tools_init.read_text(encoding="utf-8")
        except OSError:
            source = ""
        if "def create_tools" not in source:
            errors.append("tools/__init__.py has no create_tools")
    kit = plugin_id in KIT_IDS
    ok = not errors
    return {
        "ok": ok,
        "standalone": ok and not kit,
        "kit": kit,
        "plugin_id": plugin_id,
        "name": name,
        "version": version,
        "errors": errors,
        "path": str(folder),
    }


def read_origin(folder: Path) -> dict[str, Any] | None:
    path = Path(folder) / ORIGIN_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_origin(folder: Path, payload: dict[str, Any]) -> None:
    body = dict(payload)
    body["recorded_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    (Path(folder) / ORIGIN_NAME).write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def describe_source(folder: Path, plugin_id: str) -> dict[str, Any]:
    if plugin_id in KIT_IDS:
        return {"kind": "kit", "note": "Included with Kerniq."}
    origin = read_origin(folder)
    if not origin:
        return {"kind": "unknown", "note": "No source recorded, so updates cannot be checked."}
    return origin


def security_scan(root: Path) -> dict[str, Any]:
    findings: list[str] = []
    files_scanned = 0
    risk = "low"
    for py in Path(root).rglob("*.py"):
        if any(part in py.parts for part in (".git", "__pycache__", ".venv", "venv")):
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files_scanned += 1
        for pattern, label in _DANGEROUS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(f"{py.relative_to(root)}:{line_no}: {label}")
                if label in _CRITICAL:
                    risk = "critical"
                elif risk != "critical":
                    risk = "medium"
    if not (Path(root) / "manifest.toml").is_file():
        findings.append("missing manifest.toml")
        if risk == "low":
            risk = "medium"
    return {"risk": risk, "files_scanned": files_scanned, "findings": findings}


def _ignore_junk(_dir: str, names: list[str]) -> set[str]:
    skip = {"__pycache__", ".git", ".venv", "venv", ORIGIN_NAME}
    return {name for name in names if name in skip or name.endswith(".pyc")}


def _place(source: Path, dest: Path, *, force: bool) -> dict[str, Any] | None:
    if dest.exists():
        if not force:
            return {"ok": False, "error": f"Already installed: {dest.name}. Update replaces it."}
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, ignore=_ignore_junk)
    return None


def _probe_plugin(dest: Path) -> str:
    """Import the plugin class. Empty means it constructed. Does not call initialize."""
    import importlib.util
    import sys

    main_py = dest / "main.py"
    if not main_py.is_file():
        return "Plugin has no main.py."
    name = "kerniq_plugin_probe_" + dest.name
    sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(name, main_py)
    if spec is None or spec.loader is None:
        return "Plugin could not be loaded."
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, "PluginImpl", None)
        if cls is None:
            return "Plugin has no PluginImpl."
        cls()
    except SyntaxError as exc:
        return f"Syntax error in {exc.filename or main_py.name}: {exc.msg}"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"
    finally:
        sys.modules.pop(name, None)
    return ""


def adopt_plugin_archives(plugins_dir: Path | None = None) -> list[dict[str, Any]]:
    """Install plugin zip files that were dropped into the plugins folder.

    A zip that is not a plugin is left untouched. A zip that is a plugin is
    installed into its own folder and the zip is deleted.
    """
    root = plugins_root(plugins_dir)
    if not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for archive in sorted(root.iterdir()):
        if not archive.is_file() or archive.suffix.lower() != ".zip":
            continue
        if archive.name.startswith("."):
            continue
        try:
            planted = _plugin_roots_in_zip(archive)
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            results.append({"archive": archive.name, "ok": False, "kept": True, "error": str(exc)})
            continue
        if not planted:
            results.append({"archive": archive.name, "ok": False, "kept": True, "reason": "not a plugin"})
            continue
        tmp = root / f".{archive.stem}.extract"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        installed: list[str] = []
        failed = ""
        try:
            tmp.mkdir()
            with zipfile.ZipFile(archive) as zf:
                for index, prefix in enumerate(planted):
                    folder = tmp / f"part_{index}"
                    folder.mkdir()
                    _extract_prefix(zf, prefix, folder)
            for child in sorted(tmp.glob("part_*")):
                report = inspect_plugin(child)
                if not report.get("standalone"):
                    continue
                placed = install_tree(
                    child,
                    force=True,
                    plugins_dir=root,
                    origin={"kind": "archive", "file": archive.name},
                )
                if not placed.get("ok"):
                    failed = str(placed.get("error") or "install failed")
                    break
                installed.append(str(placed.get("plugin_id") or ""))
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            failed = str(exc)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
        if failed or not installed:
            results.append({
                "archive": archive.name,
                "ok": False,
                "kept": True,
                "error": failed or "not a plugin",
            })
            continue
        try:
            archive.unlink()
        except OSError as exc:
            results.append({"archive": archive.name, "ok": False, "kept": True, "error": str(exc), "installed": installed})
            continue
        results.append({"archive": archive.name, "ok": True, "kept": False, "installed": installed})
    return results


def _plugin_roots_in_zip(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as zf:
        names = [_zip_name(info.filename) for info in zf.infolist() if not info.is_dir()]
        if any(not name for name in names):
            raise ValueError("unsafe path in archive")
        roots: list[str] = []
        for name in names:
            if not name.endswith("manifest.toml"):
                continue
            prefix = name[: -len("manifest.toml")].strip("/")
            try:
                raw = zf.read(name)
                data = tomllib.loads(raw.decode("utf-8"))
            except Exception:
                continue
            block = data.get("plugin") if isinstance(data.get("plugin"), dict) else data
            plugin_id = str((block or {}).get("plugin_id") or "").strip()
            if not plugin_id or plugin_id in KIT_IDS:
                continue
            if prefix not in roots:
                roots.append(prefix)
        return roots


def _zip_name(name: str) -> str:
    text = str(name or "").replace("\\", "/")
    if text.startswith("/") or re.match(r"^[A-Za-z]:", text):
        return ""
    parts = [part for part in text.split("/") if part and part != "."]
    if ".." in parts:
        return ""
    return "/".join(parts)


def _extract_prefix(archive: zipfile.ZipFile, prefix: str, dest: Path) -> None:
    prefix = prefix.strip("/")
    for info in archive.infolist():
        name = _zip_name(info.filename)
        if not name or info.is_dir():
            continue
        if prefix:
            if name != prefix and not name.startswith(prefix + "/"):
                continue
            relative = name[len(prefix):].lstrip("/")
        else:
            relative = name
        if not relative:
            continue
        target = dest.joinpath(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, open(target, "wb") as handle:
            shutil.copyfileobj(source, handle)


def install_tree(
    source: str | Path,
    *,
    force: bool = False,
    plugins_dir: Path | None = None,
    origin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = inspect_plugin(source)
    if not report["ok"]:
        return {"ok": False, "error": "This folder is not a Kerniq plugin.", "check": report}
    if report["kit"]:
        return {"ok": False, "error": f"{report['plugin_id']} is part of the Kerniq kit and is not installed as an add-on.", "check": report}
    scan = security_scan(Path(report["path"]))
    if scan["risk"] == "critical":
        return {"ok": False, "error": "Security check failed.", "check": report, "scan": scan}
    root = plugins_root(plugins_dir)
    dest = root / report["plugin_id"]
    failed = _place(Path(report["path"]), dest, force=force)
    if failed:
        failed["check"] = report
        return failed
    recorded = dict(origin or {"kind": "path", "path": report["path"]})
    recorded["version"] = report["version"]
    recorded["plugin_id"] = report["plugin_id"]
    write_origin(dest, recorded)
    probe = _probe_plugin(dest)
    note = ""
    if scan["findings"]:
        note = " Security check noted: " + "; ".join(scan["findings"][:4]) + "."
    if probe:
        note = f" It did not load: {probe}.{note}"
    return {
        "ok": True,
        "restart": False,
        "ready": not probe,
        "status": "available" if not probe else "error",
        "plugin_id": report["plugin_id"],
        "version": report["version"],
        "path": str(dest),
        "check": report,
        "scan": scan,
        "message": (
            f"Installed {report['name']} {report['version']}. It is ready.{note}"
            if not probe
            else f"Installed {report['name']} {report['version']}, but it needs a fix.{note}"
        ),
    }


def install_github(
    repo: str,
    *,
    ref: str | None = None,
    force: bool = False,
    plugins_dir: Path | None = None,
) -> dict[str, Any]:
    parsed = parse_github_repo(repo)
    if not parsed:
        return {"ok": False, "error": "Use owner/repo or a GitHub URL."}
    owner, name = parsed
    headers = _headers()
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            if not ref:
                meta = client.get(f"{_GITHUB_API}/repos/{owner}/{name}", headers=headers)
                if meta.status_code != 200:
                    return {"ok": False, "error": f"Repo not found: {owner}/{name} ({meta.status_code})"}
                ref = meta.json().get("default_branch") or "main"
            response = client.get(f"{_GITHUB_API}/repos/{owner}/{name}/zipball/{ref}", headers=headers)
            if response.status_code != 200:
                return {"ok": False, "error": f"Download failed: HTTP {response.status_code}"}
            payload = response.content
    except httpx.HTTPError as exc:
        return {"ok": False, "error": f"Download failed: {exc}"}

    root = plugins_root(plugins_dir)
    root.mkdir(parents=True, exist_ok=True)
    tmp_root = root / f".{name}.extract"
    tmp_zip = root / f".{name}.zip"
    if tmp_root.exists():
        shutil.rmtree(tmp_root)
    try:
        tmp_zip.write_bytes(payload)
        tmp_root.mkdir()
        with zipfile.ZipFile(tmp_zip) as archive:
            archive.extractall(tmp_root)
        children = [child for child in tmp_root.iterdir() if child.is_dir()]
        unpacked = children[0] if len(children) == 1 else tmp_root
        if not (unpacked / "manifest.toml").is_file():
            nested = list(unpacked.rglob("manifest.toml"))
            if len(nested) == 1:
                unpacked = nested[0].parent
        result = install_tree(
            unpacked,
            force=force,
            plugins_dir=root,
            origin={"kind": "github", "repo": f"{owner}/{name}", "ref": ref},
        )
    except (OSError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": f"Extract failed: {exc}"}
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink(missing_ok=True)
        if tmp_root.exists():
            shutil.rmtree(tmp_root, ignore_errors=True)
    return result


def _folder_for(name: str, root: Path) -> Path | None:
    direct = root / name
    if direct.is_dir() and (direct / "manifest.toml").is_file():
        return direct
    if not root.is_dir():
        return None
    for folder in root.iterdir():
        if not folder.is_dir() or not (folder / "manifest.toml").is_file():
            continue
        try:
            data = _manifest_data(folder / "manifest.toml")
        except Exception:
            continue
        if str(data.get("plugin_id") or "") == name or folder.name == name:
            return folder
    return None


def remove_plugin(name: str, *, confirm: bool, plugins_dir: Path | None = None) -> dict[str, Any]:
    root = plugins_root(plugins_dir)
    folder = _folder_for((name or "").strip(), root)
    if folder is None:
        return {"ok": False, "error": f"Plugin not found: {name}"}
    report = inspect_plugin(folder)
    if report.get("kit") or report.get("plugin_id") in KIT_IDS:
        return {"ok": False, "error": f"{report.get('plugin_id') or folder.name} ships with Kerniq and cannot be removed."}
    if not confirm:
        return {"ok": False, "error": "Confirmation is required."}
    shutil.rmtree(folder)
    return {"ok": True, "removed": report.get("plugin_id") or folder.name, "restart": False, "message": f"Removed {folder.name}."}


def _remote_version(origin: dict[str, Any]) -> str:
    if origin.get("kind") == "path":
        report = inspect_plugin(str(origin.get("path") or ""))
        if not report.get("ok"):
            raise RuntimeError("; ".join(report.get("errors") or ["source is not a plugin"]))
        return str(report.get("version") or "")
    if origin.get("kind") != "github":
        return ""
    repo = str(origin.get("repo") or "")
    ref = str(origin.get("ref") or "main")
    url = f"https://raw.githubusercontent.com/{repo}/{ref}/manifest.toml"
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(url, headers=_headers())
    if response.status_code != 200:
        raise RuntimeError(f"GitHub returned {response.status_code} for {repo}")
    try:
        data = tomllib.loads(response.text)
    except Exception as exc:
        raise RuntimeError(f"remote manifest could not be read: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("remote manifest is empty")
    block = data.get("plugin") if isinstance(data.get("plugin"), dict) else data
    version = str((block or {}).get("version") or "").strip()
    if not version:
        raise RuntimeError("remote manifest has no version")
    return version


def _update_source(report: dict[str, Any], origin: dict[str, Any]) -> tuple[str, str]:
    """Where a newer copy would come from: a local path, or one GitHub repo."""
    if origin.get("kind") == "path" and origin.get("path"):
        return "path", str(origin.get("path") or "")
    if origin.get("kind") == "github" and origin.get("repo"):
        return "github", str(origin.get("repo") or "")
    plugin_id = str(report.get("plugin_id") or "")
    repo = OFFICIAL_REPOS.get(plugin_id) or ""
    if repo:
        return "github", repo
    return "none", ""


def check_updates(plugins_dir: Path | None = None) -> list[dict[str, Any]]:
    root = plugins_root(plugins_dir)
    rows: list[dict[str, Any]] = []
    if not root.is_dir():
        return rows
    github: list[str] = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and (path / "manifest.toml").is_file()):
        report = inspect_plugin(folder)
        origin = read_origin(folder) or {}
        kind, source = _update_source(report, origin)
        row: dict[str, Any] = {
            "plugin_id": report.get("plugin_id") or folder.name,
            "name": report.get("name") or folder.name,
            "version": report.get("version") or "",
            "kind": "kit" if report.get("kit") else (origin.get("kind") or kind),
            "repo": source if kind == "github" else (origin.get("path") or ""),
            "ref": origin.get("ref") or "",
            "update": False,
            "remote": "",
            "error": "",
            "note": "",
            "_source_kind": kind,
            "_source": source,
        }
        if kind == "github" and source and source not in github:
            github.append(source)
        rows.append(row)
    tags = None
    if github:
        from Kerniq.devtools.update_check import probe_cached

        tags = probe_cached(github)
    for row in rows:
        kind = row.pop("_source_kind")
        source = row.pop("_source")
        if kind == "none":
            if row["kind"] == "kit":
                row["note"] = "Included with Kerniq."
            else:
                row["note"] = "No source recorded, so updates cannot be checked."
            continue
        if kind == "path":
            try:
                remote = _remote_version({"kind": "path", "path": source})
            except Exception as exc:
                row["error"] = str(exc)
                continue
        else:
            if tags is None:
                row["note"] = "Update check did not answer."
                continue
            remote = str(tags.get(source) or "")
            if not remote:
                row["note"] = "No release yet."
                continue
        row["remote"] = remote
        if remote and row.get("version") and is_newer(remote, str(row.get("version"))):
            row["update"] = True
            row["note"] = f"{row.get('version')} -> {remote}"
        else:
            row["note"] = "Up to date."
    return rows


def search_repositories(query: str, limit: int = 10) -> dict[str, Any]:
    text = (query or "").strip()
    if not text:
        return {"ok": False, "error": "query is required", "repos": []}
    limit = max(1, min(int(limit or 10), 20))
    q = f"{text} kerniq plugin in:name,description,readme"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{_GITHUB_API}/search/repositories",
                params={"q": q, "sort": "stars", "order": "desc", "per_page": str(limit)},
                headers=_headers(),
            )
        if response.status_code == 403:
            return {"ok": False, "error": "GitHub API rate limited. Set GITHUB_TOKEN or retry later.", "repos": []}
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {"ok": False, "error": f"Search failed: {exc}", "repos": []}
    repos = []
    for repo in (data.get("items") or [])[:limit]:
        repos.append({
            "full_name": repo.get("full_name"),
            "description": repo.get("description") or "",
            "stars": repo.get("stargazers_count") or 0,
            "url": repo.get("html_url"),
            "default_branch": repo.get("default_branch") or "main",
        })
    return {"ok": True, "repos": repos, "query": q}
