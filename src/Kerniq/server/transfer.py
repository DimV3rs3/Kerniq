"""Download one file, or a folder, without leaving the caller's directory."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

_MAX_BYTES = 1024 * 1024 * 1024


def _safe_name(name: str) -> str:
    cleaned = name.replace("\\", "/").split("/")[-1].replace('"', "").replace("\r", "").replace("\n", "")
    return cleaned or "download"


def build_download(root: Path, target: Path) -> tuple[bytes, str, str]:
    """Return ``(body, filename, content_type)``.

    A file is sent as itself. A directory is a zip of that directory.
    The workspace root is named ``workspace.zip``. ``.kerniq-venv`` is skipped.
    """
    base = Path(root).resolve()
    chosen = Path(target).resolve()
    try:
        chosen.relative_to(base)
    except ValueError as exc:
        raise PermissionError("That path is outside /workspace.") from exc
    if not chosen.exists():
        raise FileNotFoundError("not found")
    if chosen.is_file():
        if chosen.is_symlink():
            raise PermissionError("That path is outside /workspace.")
        data = chosen.read_bytes()
        if len(data) > _MAX_BYTES:
            raise ValueError("That file is too large to download.")
        return data, _safe_name(chosen.name), "application/octet-stream"
    label = "workspace" if chosen == base else _safe_name(chosen.name)
    buf = io.BytesIO()
    total = 0
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(label + "/", "")
        for dirpath, dirnames, filenames in __import__("os").walk(chosen, followlinks=False):
            dirnames[:] = [name for name in dirnames if name != ".kerniq-venv"]
            for name in filenames:
                path = Path(dirpath) / name
                if path.is_symlink():
                    continue
                try:
                    path.resolve().relative_to(base)
                except (OSError, ValueError):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                total += size
                if total > _MAX_BYTES:
                    raise ValueError("That folder is too large to download.")
                arc = Path(label) / path.relative_to(chosen)
                archive.write(path, arc.as_posix())
    return buf.getvalue(), label + ".zip", "application/zip"
