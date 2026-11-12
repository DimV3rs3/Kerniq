"""Check GitHub releases for a newer Kerniq version."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import httpx

from Kerniq import __version__ as LOCAL_VERSION

logger = logging.getLogger(__name__)

# Public repo (may be private until published – API then needs a token)
DEFAULT_REPO = "DimV3rs3/Kerniq"
GITHUB_API = "https://api.github.com"


@dataclass
class UpdateInfo:
    local_version: str
    remote_version: Optional[str]
    release_url: Optional[str]
    release_name: Optional[str]
    is_newer: bool
    message: str
    error: Optional[str] = None


def _parse_semver(v: str) -> Tuple[int, ...]:
    """Parse leading MAJOR.MINOR.PATCH; ignore pre-release suffix for ordering."""
    v = (v or "").strip().lstrip("vV")
    m = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?", v)
    if not m:
        return (0, 0, 0)
    return tuple(int(m.group(i) or 0) for i in (1, 2, 3))


def is_newer(remote: str, local: str) -> bool:
    return _parse_semver(remote) > _parse_semver(local)


async def check_for_update(
    repo: str = DEFAULT_REPO,
    *,
    timeout: float = 15.0,
) -> UpdateInfo:
    """
    Query GitHub Releases API for the latest release tag.

    Uses GITHUB_TOKEN / GH_TOKEN when set (required for private repos).
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Kerniq-update/{LOCAL_VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 404:
                # No releases yet – fall back to tags
                tags_url = f"{GITHUB_API}/repos/{repo}/tags?per_page=1"
                tresp = await client.get(tags_url, headers=headers)
                if tresp.status_code == 404:
                    return UpdateInfo(
                        local_version=LOCAL_VERSION,
                        remote_version=None,
                        release_url=None,
                        release_name=None,
                        is_newer=False,
                        message=(
                            f"Local {LOCAL_VERSION}. Repo {repo} not found or has no releases/tags yet "
                            "(repo may still be private)."
                        ),
                        error="not_found",
                    )
                if tresp.status_code == 401 or tresp.status_code == 403:
                    return UpdateInfo(
                        local_version=LOCAL_VERSION,
                        remote_version=None,
                        release_url=None,
                        release_name=None,
                        is_newer=False,
                        message=(
                            f"Local {LOCAL_VERSION}. GitHub API returned {tresp.status_code}. "
                            "For a private repo set GITHUB_TOKEN (classic PAT with repo scope)."
                        ),
                        error="auth",
                    )
                tresp.raise_for_status()
                tags = tresp.json()
                if not tags:
                    return UpdateInfo(
                        local_version=LOCAL_VERSION,
                        remote_version=None,
                        release_url=None,
                        release_name=None,
                        is_newer=False,
                        message=f"Local {LOCAL_VERSION}. No tags on {repo} yet.",
                    )
                tag = tags[0].get("name") or ""
                newer = is_newer(tag, LOCAL_VERSION)
                return UpdateInfo(
                    local_version=LOCAL_VERSION,
                    remote_version=tag,
                    release_url=f"https://github.com/{repo}/releases",
                    release_name=tag,
                    is_newer=newer,
                    message=(
                        f"Update available: {LOCAL_VERSION} → {tag}"
                        if newer
                        else f"Up to date ({LOCAL_VERSION}; latest tag {tag})."
                    ),
                )

            if resp.status_code in (401, 403):
                return UpdateInfo(
                    local_version=LOCAL_VERSION,
                    remote_version=None,
                    release_url=None,
                    release_name=None,
                    is_newer=False,
                    message=(
                        f"Local {LOCAL_VERSION}. GitHub API returned {resp.status_code}. "
                        "Private repos need GITHUB_TOKEN / GH_TOKEN."
                    ),
                    error="auth",
                )
            resp.raise_for_status()
            data = resp.json()
            tag = data.get("tag_name") or ""
            html_url = data.get("html_url")
            name = data.get("name") or tag
            newer = is_newer(tag, LOCAL_VERSION)
            if newer:
                msg = f"Update available: {LOCAL_VERSION} → {tag}\n  {html_url}"
            else:
                msg = f"Up to date (local {LOCAL_VERSION}, latest release {tag})."
            return UpdateInfo(
                local_version=LOCAL_VERSION,
                remote_version=tag,
                release_url=html_url,
                release_name=name,
                is_newer=newer,
                message=msg,
            )
    except httpx.HTTPError as e:
        return UpdateInfo(
            local_version=LOCAL_VERSION,
            remote_version=None,
            release_url=None,
            release_name=None,
            is_newer=False,
            message=f"Local {LOCAL_VERSION}. Network error checking updates: {e}",
            error=str(e),
        )


_SKIP_ROOTS = {
    "state",
    "sessions",
    "logs",
    "workspace",
    ".git",
    ".venv",
    ".kerniq-venv",
    ".kerniq-guard",
}


def overlay_release(source: Path, dest: Path) -> None:
    """Copy a release tree onto a project without touching user data.

    ``state/``, ``sessions/``, ``logs/``, and ``workspace/`` stay. Plugin
    folders that are not in the release stay. Language packs that are not
    in the release stay. Files the release does ship, including ``ru.json``,
    are updated.
    """
    import os
    import shutil

    source = Path(source).resolve()
    dest = Path(dest).resolve()
    for dirpath, dirnames, filenames in os.walk(source):
        rel = Path(dirpath).relative_to(source)
        if rel.parts and rel.parts[0] in _SKIP_ROOTS:
            dirnames.clear()
            continue
        dirnames[:] = [name for name in dirnames if name not in {"__pycache__", ".pytest_cache"}]
        target_dir = dest / rel
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            if name.endswith(".pyc"):
                continue
            shutil.copy2(Path(dirpath) / name, target_dir / name)


def _release_root(extracted: Path) -> Path:
    children = [child for child in Path(extracted).iterdir() if child.is_dir()]
    if len(children) == 1 and (children[0] / "pyproject.toml").is_file():
        return children[0]
    if (Path(extracted) / "pyproject.toml").is_file():
        return Path(extracted)
    for child in children:
        if (child / "pyproject.toml").is_file():
            return child
    raise RuntimeError("The release archive has no project root.")


def fetch_release_zip(repo: str, dest: Path, *, timeout: float = 60.0) -> tuple[str, Path]:
    """Download the latest GitHub release zip with httpx. Does not use urllib."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Kerniq-update/{LOCAL_VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{GITHUB_API}/repos/{repo}/releases/latest"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        tag = str(data.get("tag_name") or "")
        zip_url = str(data.get("zipball_url") or "")
        if not zip_url:
            raise RuntimeError("The latest release has no zipball.")
        blob = client.get(zip_url, headers=headers)
        blob.raise_for_status()
        dest.write_bytes(blob.content)
    return tag, dest


def apply_update(
    repo: str = DEFAULT_REPO,
    *,
    preserve_state: bool = True,
) -> Tuple[bool, str]:
    """Install the latest release in place.

    Settings, sessions, logs, the workspace, user plugins, and language packs
    that are not part of the release are kept. Kit plugins and bundled
    translations are updated. ``preserve_state`` is accepted for older callers
    and is always honored.
    """
    import shutil
    import sys
    import tempfile
    import zipfile
    from pathlib import Path as _P

    del preserve_state
    try:
        from Kerniq.devtools.paths import find_project_root

        root = find_project_root()
    except Exception:
        root = None
    if root is None:
        cwd = _P.cwd()
        if (cwd / "pyproject.toml").is_file() and (cwd / "src" / "Kerniq").is_dir():
            root = cwd
    if root is None:
        return False, "Kerniq could not find the project directory to update."

    tmp = _P(tempfile.mkdtemp(prefix="kerniq-update-"))
    try:
        archive = tmp / "release.zip"
        tag, _path = fetch_release_zip(repo, archive)
        unpacked = tmp / "src"
        unpacked.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(unpacked)
        overlay_release(_release_root(unpacked), root)
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        return False, f"Update did not apply: {exc}"
    shutil.rmtree(tmp, ignore_errors=True)

    from Kerniq.sandbox.proc import hidden_run

    pip = hidden_run(
        [sys.executable, "-m", "pip", "install", "-e", str(root)],
        capture_output=True,
        text=True,
    )
    note = ((pip.stdout or "") + (pip.stderr or "")).strip()
    if pip.returncode != 0:
        return True, (
            f"Files updated to {tag or 'the latest release'}. "
            "Settings, user plugins, and language packs were kept. "
            f"Reinstall the package when you can: {note}"
        )
    return True, (
        f"Updated to {tag or 'the latest release'}. "
        "Settings, user plugins, and language packs were kept. Restart Kerniq."
    )


_PROBE_TTL = 6 * 60 * 60
_FLAGS = "auto_update.json"
_PROBE = "update_probe.json"
_busy_check = None


def set_busy_check(fn) -> None:
    """UI registers this so a restart waits until the current run finishes."""
    global _busy_check
    _busy_check = fn


def _state_dir() -> Path:
    from Kerniq.settings.loader import SettingsProvider

    return Path(SettingsProvider().config.storage.state_dir)


def load_auto_update_flags(state_dir: Path | None = None) -> dict:
    """Missing file means both switches are on."""
    directory = Path(state_dir) if state_dir is not None else _state_dir()
    path = directory / _FLAGS
    flags = {"kerniq": True, "plugins": True}
    try:
        import json
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return flags
    if isinstance(raw, dict):
        if "kerniq" in raw:
            flags["kerniq"] = bool(raw.get("kerniq"))
        if "plugins" in raw:
            flags["plugins"] = bool(raw.get("plugins"))
    return flags


def save_auto_update_flags(kerniq: bool, plugins: bool, state_dir: Path | None = None) -> dict:
    import json

    directory = Path(state_dir) if state_dir is not None else _state_dir()
    directory.mkdir(parents=True, exist_ok=True)
    flags = {"kerniq": bool(kerniq), "plugins": bool(plugins)}
    (directory / _FLAGS).write_text(json.dumps(flags, indent=2) + "\n", encoding="utf-8")
    return flags


def _headers() -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Kerniq-update/{LOCAL_VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def probe_latest(repos: list[str], *, timeout: float = 12.0) -> dict[str, str] | None:
    """One GraphQL call for every repo. None means the request failed."""
    wanted = []
    seen = set()
    for repo in repos or []:
        text = str(repo or "").strip()
        if text.count("/") != 1 or text in seen:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
            continue
        seen.add(text)
        wanted.append(text)
    if not wanted:
        return {}
    fields = []
    for index, repo in enumerate(wanted):
        owner, name = repo.split("/", 1)
        fields.append(
            f'r{index}: repository(owner: "{owner}", name: "{name}") '
            '{ latestRelease { tagName } }'
        )
    query = "query {\n" + "\n".join(fields) + "\n}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{GITHUB_API}/graphql",
                headers={**_headers(), "Content-Type": "application/json"},
                json={"query": query},
            )
        if response.status_code != 200:
            return None
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return None
        found: dict[str, str] = {}
        for index, repo in enumerate(wanted):
            node = data.get(f"r{index}") or {}
            release = node.get("latestRelease") if isinstance(node, dict) else None
            tag = ""
            if isinstance(release, dict):
                tag = str(release.get("tagName") or "")
            found[repo] = tag
        return found
    except Exception:
        logger.info("update probe failed", exc_info=False)
        return None


def _read_probe(path: Path) -> dict | None:
    import json
    import time

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        stamp = float(raw.get("at") or 0)
    except (TypeError, ValueError):
        return None
    if time.time() - stamp > _PROBE_TTL:
        return None
    tags = raw.get("tags")
    if not isinstance(tags, dict):
        return None
    return {"at": stamp, "tags": {str(k): str(v) for k, v in tags.items()}}


def _write_probe(path: Path, tags: dict[str, str]) -> None:
    import json
    import time

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"at": time.time(), "tags": tags}, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_probe_raw(path: Path) -> dict[str, str] | None:
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    tags = raw.get("tags") if isinstance(raw, dict) else None
    if not isinstance(tags, dict):
        return None
    return {str(key): str(value) for key, value in tags.items()}


def probe_cached(repos: list[str]) -> dict[str, str] | None:
    """Tags for these repos. One network call, then the same answer for six hours."""
    wanted: list[str] = []
    seen: set[str] = set()
    for repo in repos or []:
        text = str(repo or "").strip()
        if text and text not in seen:
            seen.add(text)
            wanted.append(text)
    if not wanted:
        return {}
    try:
        cache_path = _state_dir() / _PROBE
    except Exception:
        return probe_latest(wanted)
    cached = _read_probe(cache_path)
    if cached is not None and all(repo in cached["tags"] for repo in wanted):
        return cached["tags"]
    fresh = probe_latest(wanted)
    if fresh is None:
        if cached is not None:
            return cached["tags"]
        return _read_probe_raw(cache_path)
    merged: dict[str, str] = {}
    prior = cached["tags"] if cached is not None else (_read_probe_raw(cache_path) or {})
    merged.update(prior)
    merged.update(fresh)
    try:
        _write_probe(cache_path, merged)
    except OSError:
        logger.info("update probe was not saved", exc_info=False)
    return merged


def _plugin_rows():
    from Kerniq.plugins.distribution import inspect_plugin, plugins_root, read_origin
    from Kerniq.plugins.distribution import _update_source

    root = plugins_root()
    rows = []
    if not root.is_dir():
        return rows
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and (path / "manifest.toml").is_file()):
        report = inspect_plugin(folder)
        origin = read_origin(folder) or {}
        kind, source = _update_source(report, origin)
        if kind != "github" or not source:
            continue
        rows.append({
            "folder": folder,
            "plugin_id": str(report.get("plugin_id") or ""),
            "version": str(report.get("version") or ""),
            "repo": source,
        })
    return rows


def _apply_plugin_zip(row: dict, tag: str) -> bool:
    import shutil
    import tempfile
    import zipfile

    from Kerniq.plugins.distribution import inspect_plugin, write_origin

    repo = row["repo"]
    dest = Path(row["folder"])
    tmp = Path(tempfile.mkdtemp(prefix="kerniq-plugin-"))
    try:
        archive = tmp / "plugin.zip"
        headers = _headers()
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(f"{GITHUB_API}/repos/{repo}/zipball/{tag}", headers=headers)
            response.raise_for_status()
            archive.write_bytes(response.content)
        unpacked = tmp / "src"
        unpacked.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(unpacked)
        matches = []
        for manifest in unpacked.rglob("manifest.toml"):
            if any(part in {".git", "__pycache__"} for part in manifest.parts):
                continue
            report = inspect_plugin(manifest.parent)
            if report.get("plugin_id") == row["plugin_id"] and report.get("ok"):
                matches.append(manifest.parent)
        if not matches:
            return False
        source = min(matches, key=lambda path: len(path.parts))
        stage = dest.parent / f".updating-{dest.name}"
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        shutil.copytree(
            source,
            stage,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".git"),
        )
        if dest.exists():
            shutil.rmtree(dest)
        stage.rename(dest)
        write_origin(dest, {
            "kind": "github",
            "repo": repo,
            "ref": tag,
            "version": str(inspect_plugin(dest).get("version") or tag),
            "plugin_id": row["plugin_id"],
        })
        return True
    except Exception:
        logger.info("plugin update failed for %s", row.get("plugin_id"), exc_info=False)
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _wait_until_idle() -> None:
    import time

    if _busy_check is None:
        return
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        try:
            busy = bool(_busy_check())
        except Exception:
            return
        if not busy:
            return
        time.sleep(2)


def _reexec() -> None:
    import sys

    env = os.environ.copy()
    env["KERNIQ_UPDATING"] = "1"
    argv = [sys.executable, *sys.argv]
    os.execvpe(sys.executable, argv, env)


def maintain() -> None:
    """One background check. Applies what the switches allow, then restarts once."""
    if os.environ.get("KERNIQ_NO_AUTO_UPDATE", "").strip().lower() in {"1", "true", "yes"}:
        return
    if os.environ.get("KERNIQ_UPDATING") == "1":
        return
    try:
        flags = load_auto_update_flags()
    except Exception:
        return
    if not flags.get("kerniq") and not flags.get("plugins"):
        return
    repos = ["DimV3rs3/Kerniq"] if flags.get("kerniq") else []
    rows = _plugin_rows() if flags.get("plugins") else []
    for row in rows:
        if row["repo"] not in repos:
            repos.append(row["repo"])
    if not repos:
        return
    tags = probe_cached(repos)
    if not tags:
        return
    changed = False
    if flags.get("kerniq"):
        remote = tags.get("DimV3rs3/Kerniq") or ""
        if remote and is_newer(remote, LOCAL_VERSION):
            ok, _msg = apply_update()
            changed = changed or ok
    if flags.get("plugins"):
        for row in rows:
            remote = tags.get(row["repo"]) or ""
            if remote and row["version"] and is_newer(remote, row["version"]):
                if _apply_plugin_zip(row, remote):
                    changed = True
    if not changed:
        return
    logger.warning("Kerniq installed an update and is restarting.")
    _wait_until_idle()
    _reexec()
