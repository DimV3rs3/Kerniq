"""Whether a catalog model can see pictures, and how those pictures are sent.

The decision comes from a field the provider put on the model. The file name
is not a guess. The bytes go out as an image part the model can look at, not
as a text dump of the file.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

MAX_IMAGE_BYTES = 6_000_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def model_sees_images(model: dict | None) -> bool:
    """True only when the provider's own model record says it can view images."""
    if not isinstance(model, dict):
        return False
    if model.get("vision") is True:
        return True
    if _record_says_vision(model):
        return True
    raw = model.get("raw")
    return _record_says_vision(raw) if isinstance(raw, dict) else False


def _record_says_vision(model: dict) -> bool:
    caps = model.get("capabilities")
    if isinstance(caps, dict):
        if caps.get("vision") is True or caps.get("image") is True:
            return True
    elif isinstance(caps, (list, tuple)):
        for item in caps:
            if str(item).strip().lower() in {"vision", "image", "images"}:
                return True
    kind = str(model.get("type") or "").strip().lower()
    if kind in {"vlm", "vision"}:
        return True
    arch = model.get("architecture")
    if isinstance(arch, dict):
        modalities = arch.get("input_modalities") or arch.get("modalities") or []
        if isinstance(modalities, str):
            modalities = [modalities]
        if any("image" in str(item).lower() for item in modalities):
            return True
        if "image" in str(arch.get("modality") or "").lower():
            return True
    return False


def _chat_model(model: dict) -> bool:
    kind = str(model.get("type") or "").lower()
    if kind in {"embedding", "embeddings", "reranker"}:
        return False
    name = str(model.get("id") or model.get("name") or "").lower()
    return bool(name) and "embed" not in name and "rerank" not in name


def _same_model(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return False
    return a == b or a in b or b in a


async def provider_sees_images(provider) -> bool:
    """The selected model, or the one that would be picked automatically."""
    if provider is None or not hasattr(provider, "list_models"):
        return False
    try:
        listed = await provider.list_models()
    except Exception:
        return False
    rows = [row for row in listed or [] if isinstance(row, dict) and _chat_model(row)]
    chosen = str(getattr(provider, "model", "") or "").strip()
    if chosen:
        for row in rows:
            if _same_model(chosen, str(row.get("id") or row.get("name") or "")):
                return model_sees_images(row)
        return False
    for row in rows:
        if row.get("loaded_instances") or row.get("loaded_context_length"):
            return model_sees_images(row)
    return model_sees_images(rows[0]) if rows else False


def is_image_name(path: str) -> bool:
    return Path(str(path or "")).suffix.lower() in IMAGE_SUFFIXES


def sniff_image(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(raw) >= 12 and raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    if raw.startswith(b"BM"):
        return "image/bmp"
    return None


def image_record(path: Path, root: Path) -> dict[str, str] | None:
    """A picture the serializer can load later. No pixel list, no base64 yet."""
    try:
        target = Path(path).resolve()
        base = Path(root).resolve()
        if not target.is_file() or not target.is_relative_to(base):
            return None
        if target.stat().st_size <= 0 or target.stat().st_size > MAX_IMAGE_BYTES:
            return None
        mime = sniff_image(target.read_bytes()[:32])
    except OSError:
        return None
    if not mime:
        return None
    return {"path": str(target), "root": str(base), "mime": mime}


def _load_record(record: dict) -> tuple[str, str] | None:
    try:
        target = Path(str(record.get("path") or "")).resolve()
        base = Path(str(record.get("root") or "")).resolve()
        if not target.is_file() or not target.is_relative_to(base):
            return None
        if target.stat().st_size > MAX_IMAGE_BYTES:
            return None
        raw = target.read_bytes()
    except OSError:
        return None
    mime = sniff_image(raw[:32])
    if not mime:
        return None
    return mime, base64.b64encode(raw).decode("ascii")


def image_records(metadata: dict | None) -> list[dict]:
    if not isinstance(metadata, dict):
        return []
    rows = metadata.get("images")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("path")]


def openai_image_parts(metadata: dict | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for record in image_records(metadata):
        loaded = _load_record(record)
        if loaded is None:
            continue
        mime, data = loaded
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"},
        })
    return parts


def anthropic_image_parts(metadata: dict | None) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for record in image_records(metadata):
        loaded = _load_record(record)
        if loaded is None:
            continue
        mime, data = loaded
        parts.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": data},
        })
    return parts
