"""Paths the model is allowed to see.

The model always works with ./workspace and ./attachments. Real directories
on Linux, macOS, and Windows are rewritten before a tool result is returned.
Host freedom (desktop only) turns the mask off.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

VIRT_WORKSPACE = "./workspace"
VIRT_ATTACHMENTS = "./attachments"

_POSIX_ABS = re.compile(r"(?<![\w./:])/(?!/)[\w.@+-]+(?:/[\w.@+-]+)*")
_WIN_ABS = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s'\"<>|]+")
_UNC = re.compile(r"\\\\[^\s'\"<>|]+")


def alias_attachments(paths: list[str]) -> dict[str, str]:
    """Map ``./attachments/<name>`` to a real file the user attached.

    Names are unique. The real path is never part of the virtual name.
    """
    used: set[str] = set()
    out: dict[str, str] = {}
    for raw in paths:
        text = str(raw or "").replace("\\", "/").strip()
        if not text:
            continue
        path = Path(text)
        name = re.sub(r"[^\w.\-]+", "_", path.name)[:120].strip("._") or "file"
        candidate = name
        index = 2
        while candidate.lower() in used:
            if "." in name:
                stem, suffix = name.rsplit(".", 1)
                candidate = f"{stem}-{index}.{suffix}"
            else:
                candidate = f"{name}-{index}"
            index += 1
        used.add(candidate.lower())
        try:
            real = str(path.expanduser().resolve())
        except OSError:
            real = str(path)
        out[f"{VIRT_ATTACHMENTS}/{candidate}"] = real
    return out


def attachment_aliases() -> dict[str, str]:
    from Kerniq.security.task_scope import current_task

    task = current_task()
    meta = getattr(task, "metadata", None) or {} if task is not None else {}
    raw = meta.get("attachment_aliases") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(key): str(value) for key, value in raw.items() if key and value}


def rewrite_model_path(raw: str) -> str:
    """Turn a model path into a workspace-relative path or a real attachment.

    ``./workspace/a.txt`` becomes ``a.txt``. ``./attachments/a.txt`` becomes
    the attached file, or ``attachments/a.txt`` inside the workspace.
    """
    text = str(raw or "").replace("\\", "/").strip()
    aliases = attachment_aliases()
    bare = text[2:] if text.startswith("./") else text
    bare = bare.lstrip("/")
    for key in (text, "./" + bare if bare else text, bare):
        if key in aliases:
            return aliases[key]
    if bare in {"attachments", "workspace"}:
        bare_key = f"./{bare}"
        if bare_key in aliases:
            return aliases[bare_key]
    if bare == "attachments" or bare.startswith("attachments/"):
        rest = bare[len("attachments") :].lstrip("/")
        virt = f"{VIRT_ATTACHMENTS}/{rest}" if rest else VIRT_ATTACHMENTS
        if virt in aliases:
            return aliases[virt]
        return f"attachments/{rest}" if rest else "attachments"
    if bare == "downloads" or bare.startswith("downloads/") or bare == ".downloads" or bare.startswith(".downloads/"):
        rest = bare.split("/", 1)[1] if "/" in bare else ""
        return f".downloads/{rest}" if rest else ".downloads"
    if bare == ".kerniq-view":
        return "."
    if bare.startswith(".kerniq-view/"):
        return rewrite_model_path(bare.split("/", 1)[1])
    if bare == "workspace" or bare.startswith("workspace/"):
        rest = bare[len("workspace") :].lstrip("/")
        return rest or "."
    return raw


def _variants(path: str) -> list[str]:
    text = str(path or "")
    if not text or text in {".", "/", "\\"}:
        return []
    found = [text]
    flipped = text.replace("\\", "/") if "\\" in text else text.replace("/", "\\")
    if flipped != text:
        found.append(flipped)
    return found


def _known_replacements(workspace: Path | str | None) -> list[tuple[str, str]]:
    from Kerniq.server.homes import jail_root

    pairs: list[tuple[str, str]] = []
    jail = jail_root()
    if jail is not None:
        try:
            root = Path(jail).resolve()
        except OSError:
            root = Path(jail)
        pairs.append((str(root / "workspace"), VIRT_WORKSPACE))
        pairs.append((str(root / "attachments"), VIRT_ATTACHMENTS))
        pairs.append((str(root), "."))
    if workspace is not None:
        try:
            ws = Path(workspace).resolve()
        except OSError:
            ws = Path(workspace)
        if jail is None or Path(str(jail)).resolve() != ws:
            pairs.append((str(ws / ".downloads"), "./downloads"))
            pairs.append((str(ws / "attachments"), VIRT_ATTACHMENTS))
            pairs.append((str(ws), VIRT_WORKSPACE))
        else:
            pairs.append((str(ws / ".downloads"), "./downloads"))
            pairs.append((str(Path(jail) / "downloads"), "./downloads"))
        try:
            from Kerniq.security.roots import desktop_roots

            roots = desktop_roots(ws)
            pairs.append((str(roots.downloads), "./downloads"))
            pairs.append((str(roots.attachments), VIRT_ATTACHMENTS))
        except Exception:
            pass
    for virtual, real in attachment_aliases().items():
        pairs.append((real, virtual))
    try:
        home = str(Path.home())
    except OSError:
        home = ""
    if home:
        pairs.append((home, "[private]"))
    try:
        from Kerniq.devtools.paths import find_project_root

        project = find_project_root()
    except Exception:
        project = None
    if project is not None:
        pairs.append((str(project), "[private]"))
    return [(real, virt) for real, virt in pairs if real and real not in {".", "/", "\\"}]


def scrub_for_model(
    text: str,
    *,
    workspace: Path | str | None = None,
    reveal: bool = False,
) -> str:
    """Replace host paths. ``reveal`` is host freedom and returns the text unchanged."""
    if text is None:
        return ""
    if reveal or not str(text):
        return str(text)
    out = str(text)
    pairs = _known_replacements(workspace)
    # Longest real path first so a workspace prefix wins over $HOME.
    expanded: list[tuple[str, str]] = []
    for real, virt in pairs:
        for variant in _variants(real):
            expanded.append((variant, virt))
    expanded.sort(key=lambda item: len(item[0]), reverse=True)
    seen: set[str] = set()
    for real, virt in expanded:
        if real in seen or len(real) < 2:
            continue
        seen.add(real)
        if os.name == "nt":
            out = re.sub(re.escape(real), virt, out, flags=re.IGNORECASE)
        else:
            out = out.replace(real, virt)
    out = _UNC.sub("[outside]", out)
    out = _WIN_ABS.sub("[outside]", out)
    out = _POSIX_ABS.sub("[outside]", out)
    return out


def is_absolute_text(raw: str) -> bool:
    """True for ``/``, ``C:\\``, and ``\\\\server`` – including on Windows, where ``Path('/')`` is not absolute."""
    text = str(raw or "").strip()
    if not text:
        return False
    try:
        if Path(text).is_absolute():
            return True
    except OSError:
        pass
    norm = text.replace("\\", "/")
    if norm.startswith("/"):
        return True
    return len(norm) >= 2 and norm[1] == ":"


def resolve_unconfined(raw: str, workspace: Path | str) -> Path:
    """A real path once host freedom is already on.

    ``.`` and ``./workspace`` stay the workspace. ``/``, ``C:\\`` and ``..``
    may leave it. Virtual ``./attachments`` still hits the attachments folder.
    """
    text = str(raw or "").strip() or "."
    root = Path(workspace)
    folded = text.replace("\\", "/")
    if folded in {".", "./", "workspace", "./workspace"}:
        return root.resolve()
    if is_absolute_text(text):
        path = Path(text).expanduser()
        try:
            return path.resolve()
        except OSError:
            return path.absolute()
    from Kerniq.security.roots import resolve_virtual

    try:
        mapped = resolve_virtual(text, root)
    except PermissionError:
        mapped = None
    if mapped is not None:
        return mapped
    path = (root / Path(text)).expanduser()
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _host_open(policy) -> bool:
    opener = getattr(policy, "host_is_open", None)
    return bool(opener()) if callable(opener) else False


def terminal_cwd(requested: str, policy) -> Path:
    """Where a shell starts. ``.`` is the link view, not a copy of the workspace.

    Host freedom is decided first. An open host may start in ``/`` or on another
    drive. A view that cannot be created (Windows symlink privilege) falls back
    to the workspace instead of pretending the path left it.
    """
    from Kerniq.security.roots import ensure_view
    from Kerniq.server.homes import downloads_folder, jail_root, logical_path

    jail = jail_root()
    original = str(requested or ".").strip() or "."
    text = original.replace("\\", "/").strip() or "."
    workspace = Path(policy.workspace_root)
    if _host_open(policy) and jail is None:
        # The link view is the cage. An open host starts in the real workspace
        # and may point cwd at ``/`` or another drive.
        if text in {".", "./", ""}:
            return workspace.resolve()
        return resolve_unconfined(original, workspace)
    if jail is not None:
        if text in {".", "./", ""}:
            root = Path(jail)
            return ensure_view(
                root / "workspace",
                attachments=root / "attachments",
                downloads=downloads_folder(root),
            )
        return logical_path(text, Path(jail))
    if text in {".", "./", "", ".kerniq-view", "./.kerniq-view"}:
        try:
            return ensure_view(workspace)
        except Exception:
            return workspace.resolve()
    return policy.validate_path(text)
