"""One folder per browser user. The folder cannot see the rest of the machine."""

from __future__ import annotations

import contextvars
import os
import time
from pathlib import Path
from typing import Any

DISPLAY_ROOT = "/workspace"
VIRT_WORKSPACE = "./workspace"
VIRT_ATTACHMENTS = "./attachments"
_DEFAULT_QUOTA = 8 * 1024 * 1024 * 1024
_MIN_QUOTA = 32 * 1024 * 1024
_quota: contextvars.ContextVar[dict | None] = contextvars.ContextVar("kerniq_disk_quota", default=None)
_jail: contextvars.ContextVar[Path | None] = contextvars.ContextVar("kerniq_user_jail", default=None)
_usage_cache: dict[str, tuple[float, int]] = {}
_SAFE = __import__("re").compile(r"[^a-zA-Z0-9_-]+")


def safe_user_dir(user_id: str) -> str:
    cleaned = _SAFE.sub("_", user_id or "user").strip("._")
    return (cleaned or "user")[:80]


def users_root(state_dir: Path | str, core: dict | None = None) -> Path:
    """Primary folder for new homes. Empty means <project>/workspace."""
    roots = user_roots(state_dir, core)
    return roots[0]


def user_roots(state_dir: Path | str, core: dict | None = None) -> list[Path]:
    """Every disk the admin offered. The first entry is the primary root.

    An existing cookie folder is reused wherever it already lives. A new
    folder is created on the root with the most free space.
    """
    from ..devtools.paths import anchored_dir, find_project_root

    core = core or {}
    raw = str(core.get("users_root") or "").strip()
    if raw:
        primary = Path(raw).expanduser().resolve()
    else:
        project = find_project_root()
        if project is None:
            project = anchored_dir(state_dir).parent
        primary = (project / "workspace").resolve()
    primary.mkdir(parents=True, exist_ok=True)
    if not raw:
        _adopt_legacy_homes(state_dir, primary)
    roots = [primary]
    seen = {str(primary)}
    for extra in core.get("users_roots") or []:
        text = str(extra or "").strip()
        if not text:
            continue
        try:
            folder = assert_users_root(text)
        except ValueError:
            continue
        key = str(folder)
        if key in seen:
            continue
        seen.add(key)
        roots.append(folder)
    return roots


def _free_bytes(folder: Path) -> int:
    try:
        return int(os.statvfs(folder).f_bavail * os.statvfs(folder).f_frsize)
    except (AttributeError, OSError):
        try:
            import shutil

            return int(shutil.disk_usage(folder).free)
        except OSError:
            return 0


def user_home(state_dir: Path | str, user_id: str, core: dict | None = None) -> Path:
    """Create this user's private environment.

    Layout, under whichever root already holds the cookie or has room::

        <cookie-id>/workspace
        <cookie-id>/attachments

    Older releases stored files directly in the cookie folder. Those files
    move into workspace/ once. The cookie id is not shown to the model.
    """
    roots = user_roots(state_dir, core)
    name = safe_user_dir(user_id)
    for root in roots:
        folder = (root / name).resolve()
        try:
            folder.relative_to(root)
        except ValueError:
            continue
        if folder.is_dir():
            return ensure_user_layout(folder)
    best = max(roots, key=_free_bytes)
    folder = (best / name).resolve()
    try:
        folder.relative_to(best)
    except ValueError as exc:
        raise PermissionError("User folder escapes the home root.") from exc
    folder.mkdir(parents=True, exist_ok=True)
    return ensure_user_layout(folder)


def gather_stray_workspace(dest: Path, relative: Path | str) -> Path:
    """Put a cwd-relative workspace into the project one.

    Launching from ``scripts/`` used to create ``scripts/workspace``. The
    project folder is the one that stays. Existing names are not overwritten.
    """
    import shutil

    folder = Path(dest).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    raw = Path(relative)
    if raw.is_absolute():
        return folder
    try:
        stray = (Path.cwd() / raw).resolve()
    except OSError:
        return folder
    if stray == folder or not stray.is_dir():
        return folder
    for child in list(stray.iterdir()):
        if child.name == ".kerniq-venv":
            continue
        target = folder / child.name
        if target.exists():
            continue
        try:
            child.rename(target)
        except OSError:
            shutil.move(str(child), str(target))
    return folder


def _adopt_legacy_homes(state_dir: Path | str, root: Path) -> None:
    """Move state/homes/<id> into the project workspace once. An admin root is left alone."""
    import shutil

    from ..devtools.paths import anchored_dir

    legacy = anchored_dir(state_dir) / "homes"
    try:
        if not legacy.is_dir() or legacy.resolve() == root.resolve():
            return
    except OSError:
        return
    for child in list(legacy.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        dest = root / child.name
        if dest.exists():
            continue
        try:
            child.rename(dest)
        except OSError:
            shutil.move(str(child), str(dest))


def assert_users_root(path: str) -> Path:
    """Refuse the filesystem root and other places that are not a home folder."""
    root = Path(path).expanduser().resolve()
    anchor = Path(root.anchor)
    if root == anchor:
        raise ValueError("The user-folder root cannot be the disk root.")
    blocked = {"/etc", "/usr", "/bin", "/sbin", "/proc", "/sys", "/dev", "/boot", "/root", "/home"}
    if root.as_posix().rstrip("/") in blocked:
        raise ValueError("That path is not a place for user folders.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_user_layout(folder: Path) -> Path:
    """Create workspace/ and attachments/ and move loose files into workspace/."""
    import shutil

    root = Path(folder).resolve()
    workspace = root / "workspace"
    attachments = root / "attachments"
    workspace.mkdir(parents=True, exist_ok=True)
    attachments.mkdir(parents=True, exist_ok=True)
    keep = {"workspace", "attachments", ".kerniq-venv", ".kerniq-guard"}
    for child in list(root.iterdir()):
        if child.name in keep or child.name.startswith("."):
            continue
        dest = workspace / child.name
        if dest.exists():
            continue
        try:
            child.rename(dest)
        except OSError:
            shutil.move(str(child), str(dest))
    return root


def quota_bytes(core: dict | None) -> int:
    raw = (core or {}).get("user_quota_bytes")
    try:
        size = int(raw)
    except (TypeError, ValueError):
        size = _DEFAULT_QUOTA
    if size < _MIN_QUOTA:
        size = _DEFAULT_QUOTA
    return size


def usage_bytes(folder: Path) -> int:
    key = str(folder)
    now = time.monotonic()
    hit = _usage_cache.get(key)
    if hit and now - hit[0] < 5:
        return hit[1]
    total = 0
    for dirpath, dirnames, filenames in os.walk(folder, followlinks=False):
        dirnames[:] = [name for name in dirnames if name != ".kerniq-venv"]
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
    _usage_cache[key] = (now, total)
    return total


def quota_status(folder: Path, limit: int) -> dict[str, Any]:
    used = usage_bytes(folder)
    return {
        "used": used,
        "limit": int(limit),
        "near": used >= int(limit * 0.9),
        "full": used >= int(limit),
    }


def set_quota(status: dict | None):
    return _quota.set(status)


def reset_quota(token) -> None:
    _quota.reset(token)


def bind_jail(folder: Path | None):
    """Remember whose folder this thread may touch. The browser only sees /workspace."""
    if folder is None:
        return _jail.set(None)
    return _jail.set(Path(folder).resolve())


def reset_jail(token) -> None:
    _jail.reset(token)


def jail_root() -> Path | None:
    return _jail.get()


def display_path(path: Path | str, root: Path | None = None) -> str:
    """Hide the real directory. The model sees ./workspace or ./attachments."""
    root = Path(root).resolve() if root is not None else _jail.get()
    if root is None:
        return str(path)
    try:
        resolved = Path(path).resolve()
    except OSError:
        resolved = Path(path)
    try:
        rel = resolved.relative_to(Path(root).resolve())
    except ValueError:
        return VIRT_WORKSPACE
    parts = rel.parts
    if not parts or parts == (".",):
        return "."
    head, rest = parts[0], "/".join(parts[1:])
    if head == "workspace":
        return VIRT_WORKSPACE if not rest else VIRT_WORKSPACE + "/" + rest
    if head == "attachments":
        return VIRT_ATTACHMENTS if not rest else VIRT_ATTACHMENTS + "/" + rest
    return VIRT_WORKSPACE + "/" + rel.as_posix()


def _virtual_bucket(text: str) -> tuple[str, str]:
    """Return ``(workspace|attachments, remainder)`` for a model path."""
    norm = str(text or "").replace("\\", "/").strip()
    while norm.startswith("./"):
        norm = norm[2:]
    if norm.startswith("/"):
        norm = norm.lstrip("/")
    for bucket in ("workspace", "attachments"):
        if norm == bucket:
            return bucket, ""
        prefix = bucket + "/"
        if norm.startswith(prefix):
            return bucket, norm[len(prefix) :]
    return "workspace", norm


def logical_path(raw: str, root: Path) -> Path:
    """Map a browser or model path into this user's workspace or attachments.

    ``/workspace/notes/a.txt``, ``./workspace/notes/a.txt`` and ``notes/a.txt``
    all land in ``<cookie>/workspace``. ``./attachments/...`` lands beside it.
    A real disk path, a symlink that leaves the folder, or ``..`` that climbs
    out is refused. The error does not repeat the machine path.
    """
    text = str(raw or "").replace("\\", "/").strip()
    if "\x00" in text or text.startswith("//") or text.startswith("\\\\"):
        raise PermissionError("That path is outside ./workspace.")
    if len(text) > 2 and text[1] == ":":
        raise PermissionError("That path is outside ./workspace.")
    if text.startswith("/") and not (
        text == DISPLAY_ROOT
        or text.startswith(DISPLAY_ROOT + "/")
        or text == "/attachments"
        or text.startswith("/attachments/")
    ):
        raise PermissionError("That path is outside ./workspace.")
    bucket, rest = _virtual_bucket(text)
    if rest.startswith("/") or ".." in Path(rest).parts:
        raise PermissionError("That path is outside ./workspace.")
    base = (Path(root).resolve() / bucket).resolve()
    target = base if not rest else (base / rest).resolve()
    try:
        target.relative_to(base)
        target.relative_to(Path(root).resolve())
    except ValueError as exc:
        raise PermissionError("That path is outside ./workspace.") from exc
    return target


def write_blocked_reason() -> str:
    status = _quota.get()
    if not status or not status.get("full"):
        return ""
    limit = int(status.get("limit") or _DEFAULT_QUOTA)
    gib = max(1, round(limit / (1024 * 1024 * 1024)))
    return (
        f"This workspace is full. The limit is {gib} GB. "
        "Do not write files. Ask the user what to delete."
    )


def admit_bytes(new_bytes: int, old_bytes: int = 0) -> str:
    """Refuse a write that would pass the user's limit. Empty means it fits."""
    status = _quota.get()
    folder = _jail.get()
    if not status or folder is None:
        return ""
    limit = int(status.get("limit") or _DEFAULT_QUOTA)
    used = usage_bytes(folder)
    projected = used - max(0, int(old_bytes)) + max(0, int(new_bytes))
    if projected > limit:
        fresh = {"used": used, "limit": limit, "near": True, "full": True}
        _quota.set(fresh)
        return write_blocked_reason()
    fresh = {
        "used": projected,
        "limit": limit,
        "near": projected >= int(limit * 0.9),
        "full": False,
    }
    _quota.set(fresh)
    _usage_cache[str(folder)] = (time.monotonic(), projected)
    return ""


def invalidate_usage(folder: Path | None = None) -> None:
    if folder is None:
        _usage_cache.clear()
        return
    _usage_cache.pop(str(folder), None)


def disk_note(status: dict | None) -> str:
    if not status or not (status.get("near") or status.get("full")):
        return ""
    used = int(status.get("used") or 0) / (1024 * 1024 * 1024)
    limit = int(status.get("limit") or _DEFAULT_QUOTA) / (1024 * 1024 * 1024)
    if status.get("full"):
        return (
            f"The user disk is full ({used:.2f} GB of {limit:.0f} GB). "
            "Do not create or edit files. Tell the user and decide with them what to remove."
        )
    return (
        f"The user disk is nearly full ({used:.2f} GB of {limit:.0f} GB). "
        "Before a large write, tell the user and agree what to drop."
    )


LOCAL_PROVIDERS = {"lm_studio", "ollama"}


def _host_of(url: str) -> str:
    text = (url or "").strip()
    start = text.find("://")
    name = text[start + 3 :] if start >= 0 else text
    return name.split("/", 1)[0].split("@")[-1].strip()


def _hostname(url: str) -> str:
    host = _host_of(url)
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end > 1 else host
    return host.split(":", 1)[0]


def is_loopback_url(url: str) -> bool:
    name = _hostname(url).lower()
    return name in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_private_url(url: str) -> bool:
    """Loopback, link-local, and LAN addresses. A browser must not aim the server at these."""
    if is_loopback_url(url):
        return True
    name = _hostname(url).lower()
    if name.startswith("10.") or name.startswith("192.168.") or name.startswith("169.254."):
        return True
    if name.startswith("172."):
        parts = name.split(".")
        if len(parts) >= 2 and parts[1].isdigit():
            return 16 <= int(parts[1]) <= 31
    return name in {"metadata.google.internal"} or name.endswith(".local")


def loopback_sibling(url: str) -> str:
    """Same port on 127.0.0.1 when the configured host is not already loopback."""
    text = (url or "").strip().rstrip("/")
    if not text or is_loopback_url(text):
        return ""
    host = _host_of(text)
    port = ""
    if host.startswith("["):
        return ""
    if ":" in host:
        _name, _, port = host.rpartition(":")
    scheme = "https" if text.lower().startswith("https://") else "http"
    suffix = f":{port}" if port else ""
    return f"{scheme}://127.0.0.1{suffix}"


def provider_base_url(saved: str, provider: str, core: dict | None, *, server_mode: bool) -> str:
    """In server mode a local model is reached from this machine, not from the browser."""
    if server_mode and (provider or "lm_studio") in LOCAL_PROVIDERS:
        admin = str((core or {}).get("model_base_url") or "").strip()
        return (admin or "http://127.0.0.1:1234").rstrip("/")
    text = (saved or "").strip()
    return text or "http://127.0.0.1:1234"


def _is_metadata_url(url: str) -> bool:
    """Link-local and cloud metadata hosts. Never a model endpoint."""
    name = _hostname(url).lower()
    return name.startswith("169.254.") or name in {"metadata.google.internal"}


def hide_unused_base_url(ui: Any) -> Any:
    """Drop a base URL the selected provider does not ask for.

    A saved LM Studio address must not follow the user onto a cloud provider.
    Server mode would otherwise refuse it as a private URL.
    """
    api = getattr(ui, "api", None)
    if api is None:
        return ui
    from Kerniq.models.catalog import spec_by_id

    provider = str(getattr(api, "provider", "") or "")
    spec = spec_by_id(provider)
    if not spec:
        return ui
    keys = {str(f.get("key") or "") for f in (spec.get("fields") or [])}
    if "base_url" not in keys:
        api.base_url = ""
    return ui


def lock_model_api(ui: Any, core: dict | None) -> Any:
    """Keep the URL and key the user saved. Block metadata and private cloud URLs.

    LM Studio and Ollama may use a LAN address: that is where a local server
    usually sits, and the browser is not talking to it directly. An empty
    local URL falls back to the admin ``model_base_url``. A cloud provider
    still cannot be aimed at a private address.
    """
    api = getattr(ui, "api", None)
    if api is None:
        return ui
    provider = str(getattr(api, "provider", None) or "lm_studio")
    if provider in LOCAL_PROVIDERS:
        typed = str(getattr(api, "base_url", "") or "").strip()
        if typed and _is_metadata_url(typed):
            raise PermissionError("That address is not a model endpoint.")
        if not typed:
            api.base_url = provider_base_url("", provider, core, server_mode=True)
        return ui
    base = str(getattr(api, "base_url", "") or "")
    if base and (is_private_url(base) or _is_metadata_url(base)):
        raise PermissionError(
            "In server mode a browser cannot point a model at a private address. "
            "Use the provider's public URL."
        )
    return ui


def local_model_candidates(admin_url: str, saved_url: str = "") -> list[str]:
    """Admin URL first, then loopback on that port, then a saved loopback URL."""
    found: list[str] = []

    def add(url: str) -> None:
        text = (url or "").strip().rstrip("/")
        if text and text not in found:
            found.append(text)

    add(admin_url or "http://127.0.0.1:1234")
    add(loopback_sibling(found[0] if found else ""))
    if is_loopback_url(saved_url):
        add(saved_url)
    return found or ["http://127.0.0.1:1234"]
