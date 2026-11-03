"""Virtual roots the model sees: workspace, attachments, and downloads.

`.kerniq-view` is a directory of symlinks. It is never created inside a
directory it links to. That cycle is what made the view copy itself forever
when the workspace was the Kerniq source tree.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

VIEW_NAME = ".kerniq-view"
ROOTS = ("workspace", "attachments", "downloads")


@dataclass(frozen=True)
class ModelRoots:
    workspace: Path
    attachments: Path
    downloads: Path
    view: Path

    def as_list(self) -> list[Path]:
        return [self.workspace, self.attachments, self.downloads]


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def model_roots(workspace) -> ModelRoots:
    """Physical folders for one desktop workspace. The view is a sibling.

    Attachments and downloads stay inside the workspace unless
    ``desktop_roots`` is used. Tests rely on that layout.
    """
    ws = Path(workspace).expanduser()
    if not ws.is_absolute():
        ws = Path.cwd() / ws
    ws = _resolved(ws)
    return ModelRoots(
        workspace=ws,
        attachments=ws / "attachments",
        downloads=ws / ".downloads",
        view=_view_path(ws),
    )


def install_anchor() -> Path | None:
    """Kerniq install directory. Empty or unset means "not the live app"."""
    raw = (os.environ.get("KERNIQ_ROOT") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _peek_folder_settings() -> tuple[str, str]:
    """Saved attachment and download locations. Does not rewrite settings."""
    att, down = "./attachments", "./downloads"
    try:
        from Kerniq.settings.file import read_settings_file
        from Kerniq.settings.loader import SettingsProvider

        state = SettingsProvider().config.storage.state_dir
        raw = read_settings_file(state) or {}
        agent = raw.get("agent") if isinstance(raw, dict) else None
        if isinstance(agent, dict):
            att = str(agent.get("attachments") or att).strip() or "./attachments"
            down = str(agent.get("downloads") or down).strip() or "./downloads"
    except Exception:
        pass
    return att, down


def _resolve_data_dir(value: str, anchor: Path, default: str) -> Path:
    text = (value or "").strip() or default
    if text in {".", "./"}:
        text = default
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = anchor / path
    return _resolved(path)


def desktop_roots(workspace) -> ModelRoots:
    """Attachments and downloads do not follow the workspace.

    ``./attachments`` and ``./downloads`` are next to the installed Kerniq
    (``KERNIQ_ROOT``). An absolute setting is used as written. With no install
    root the in-workspace layout from ``model_roots`` stays.
    """
    anchor = install_anchor()
    if anchor is None:
        return model_roots(workspace)
    base = model_roots(workspace)
    att, down = _peek_folder_settings()
    return ModelRoots(
        workspace=base.workspace,
        attachments=_resolve_data_dir(att, anchor, "attachments"),
        downloads=_resolve_data_dir(down, anchor, "downloads"),
        view=base.view,
    )


def is_view_root(raw: str) -> bool:
    text = str(raw or "").replace("\\", "/").strip()
    return text in {"", ".", "./", VIEW_NAME, "./" + VIEW_NAME}


def _inside(path: Path, root: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(root))
    except ValueError:
        return False
    return True


def _view_path(workspace: Path) -> Path:
    parent = workspace.parent
    preferred = parent / VIEW_NAME
    if parent == workspace or _inside(preferred, workspace):
        digest = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:12]
        return Path.home() / ".kerniq" / "views" / digest
    if preferred.exists() and not _view_matches(preferred, workspace):
        digest = hashlib.sha256(str(workspace).encode("utf-8")).hexdigest()[:12]
        return parent / f".kerniq-view-{digest}"
    return preferred


def _view_matches(view: Path, workspace: Path) -> bool:
    link = view / "workspace"
    if not link.exists() and not link.is_symlink():
        return True
    if not link.is_symlink():
        return False
    try:
        return _resolved(link) == _resolved(workspace)
    except OSError:
        return False


def _looks_like_view(path: Path) -> bool:
    if path.is_symlink():
        return path.name == VIEW_NAME
    if not path.is_dir():
        return False
    try:
        names = {child.name for child in path.iterdir()}
    except OSError:
        return False
    return "workspace" in names and bool(names & {"attachments", "downloads"})


def _remove_tree(path: Path, depth: int = 0) -> None:
    """Delete a view without following a symlink back into itself."""
    if depth > 6:
        return
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if not path.is_dir():
        return
    for child in list(path.iterdir()):
        _remove_tree(child, depth + 1)
    path.rmdir()


def prune_nested_view(workspace: Path) -> None:
    """Remove a `.kerniq-view` that was created inside the workspace."""
    nested = Path(workspace) / VIEW_NAME
    if not nested.exists() and not nested.is_symlink():
        return
    if nested.is_symlink() or _looks_like_view(nested):
        _remove_tree(nested)


def _link(link: Path, target: Path) -> None:
    view = link.parent
    if _inside(view, target):
        raise RuntimeError("Refusing a .kerniq-view link that contains the view.")
    if link.is_symlink():
        try:
            if _resolved(link) == _resolved(target):
                return
        except OSError:
            pass
        link.unlink()
    elif link.exists():
        if _looks_like_view(link) or link.name in ROOTS:
            _remove_tree(link)
        else:
            return
    link.symlink_to(target, target_is_directory=True)


def ensure_view(workspace, *, attachments: Path | None = None, downloads: Path | None = None) -> Path:
    """Create three symlinks. Does not copy files."""
    if attachments is None and downloads is None:
        roots = desktop_roots(workspace)
    else:
        roots = model_roots(workspace)
    prune_nested_view(roots.workspace)
    att = Path(attachments) if attachments is not None else roots.attachments
    down = Path(downloads) if downloads is not None else roots.downloads
    att.mkdir(parents=True, exist_ok=True)
    down.mkdir(parents=True, exist_ok=True)
    view = roots.view if attachments is None and downloads is None else _view_path(roots.workspace)
    if attachments is not None or downloads is not None:
        # Server homes keep the view next to workspace/, still outside it.
        if not _inside(roots.workspace.parent / VIEW_NAME, roots.workspace):
            view = roots.workspace.parent / VIEW_NAME
    view.mkdir(parents=True, exist_ok=True)
    _link(view / "workspace", roots.workspace)
    _link(view / "attachments", att)
    _link(view / "downloads", down)
    return view


def resolve_virtual(raw: str, workspace) -> Path | None:
    """Map a model path onto a real file. None means the caller owns an absolute path."""
    from Kerniq.server.homes import jail_root, logical_path

    jail = jail_root()
    if jail is not None:
        return logical_path(str(raw or ""), jail)
    text = str(raw or "").replace("\\", "/").strip()
    if not text or "\x00" in text or text.startswith("\\\\") or text.startswith("//"):
        raise PermissionError("That path is outside the workspace.")
    if len(text) > 2 and text[1] == ":":
        return None
    if text.startswith("/") and not text.startswith(("/workspace", "/attachments", "/downloads", "/.kerniq-view")):
        return None
    roots = desktop_roots(workspace)
    bare = text[2:] if text.startswith("./") else text
    bare = bare.lstrip("/")
    if bare == VIEW_NAME:
        return ensure_view(roots.workspace)
    if bare.startswith(VIEW_NAME + "/"):
        return resolve_virtual(bare.split("/", 1)[1], roots.workspace)
    bucket = ""
    rest = bare
    for name in ROOTS:
        if bare == name:
            bucket, rest = name, ""
            break
        prefix = name + "/"
        if bare.startswith(prefix):
            bucket, rest = name, bare[len(prefix):]
            break
    if bare == ".downloads" or bare.startswith(".downloads/"):
        bucket, rest = "downloads", bare.split("/", 1)[1] if "/" in bare else ""
    bases = {
        "workspace": roots.workspace,
        "attachments": roots.attachments,
        "downloads": roots.downloads,
    }
    if not bucket:
        if text.startswith("/"):
            return None
        return _join(roots.workspace, bare)
    return _join(bases[bucket], rest)


def _join(base: Path, rest: str) -> Path:
    if rest in {"", "."}:
        return base
    cur = base
    for part in Path(rest.replace("\\", "/")).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if cur == base:
                raise PermissionError("That path is outside the workspace.")
            cur = cur.parent
            continue
        cur = cur / part
    probe = cur
    while not probe.exists() and probe != base:
        probe = probe.parent
    try:
        _resolved(probe).relative_to(_resolved(base))
    except ValueError as exc:
        raise PermissionError("That path is outside the workspace.") from exc
    if cur.exists() or cur.is_symlink():
        try:
            _resolved(cur).relative_to(_resolved(base))
        except ValueError as exc:
            raise PermissionError("That path is outside the workspace.") from exc
    return cur


def shown_virtual(path, workspace) -> str:
    roots = desktop_roots(workspace)
    try:
        resolved = _resolved(Path(path))
    except OSError:
        resolved = Path(path)
    pairs = (
        (roots.downloads, "./downloads"),
        (roots.attachments, "./attachments"),
        (roots.workspace, "./workspace"),
    )
    for folder, label in pairs:
        try:
            rel = resolved.relative_to(_resolved(folder))
        except ValueError:
            continue
        text = rel.as_posix()
        if text in {"", "."}:
            return label
        return label + "/" + text
    return ""
