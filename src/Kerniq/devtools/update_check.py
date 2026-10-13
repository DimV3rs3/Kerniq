"""Check GitHub releases for a newer Kerniq version."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
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


def apply_update(
    repo: str = DEFAULT_REPO,
    *,
    preserve_state: bool = True,
) -> Tuple[bool, str]:
    """
    Install the latest published version without wiping user settings.

    Strategy (editable local tree preferred):
    1. If we are inside a git checkout of Kerniq → git pull + pip install -e ".[dev,mcp]"
    2. Else pip install from GitHub archive / PyPI name Kerniq

    state/ sessions/ logs/ and component settings under the project or user
    site are not deleted.
    """
    import subprocess
    import sys
    from pathlib import Path as _P

    def run(cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out

    # Locate project root (editable install)
    root = None
    try:
        from Kerniq.devtools.paths import find_project_root
        root = find_project_root()
    except Exception:
        root = None
    if root is None:
        cwd = _P.cwd()
        if (cwd / "pyproject.toml").is_file():
            root = cwd

    if root and (root / ".git").exists():
        code, out = run(["git", "-C", str(root), "pull", "--ff-only"])
        if code != 0:
            # continue with pip anyway
            pass
        code2, out2 = run([
            sys.executable, "-m", "pip", "install", "-e", f"{root}[dev,mcp]",
        ])
        ok = code2 == 0
        return ok, out2 or out or ("updated from git " + str(root))

    # Fallback: pip from GitHub
    url = f"git+https://github.com/{repo}.git"
    code, out = run([
        sys.executable, "-m", "pip", "install", "--upgrade", f"{url}#egg=Kerniq",
    ])
    if code != 0:
        code, out = run([sys.executable, "-m", "pip", "install", "--upgrade", "Kerniq"])
    return code == 0, out
