"""Check GitHub releases for a newer Kerniq version."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import httpx

from Kerniq import __version__ as LOCAL_VERSION

# Public repo (may be private until published — API then needs a token)
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
                # No releases yet — fall back to tags
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
