"""Model identity. Two catalog ids match only when they are the same string.

LM Studio can load ``gemma`` and ``gemma-qat`` at the same time. A prefix or
family match would treat them as one model and load or unload the wrong one.
"""

from __future__ import annotations


def same_model(left: str, right: str) -> bool:
    a = (left or "").strip()
    b = (right or "").strip()
    return bool(a) and a == b


def instance_model_key(model_id: str) -> str:
    """Catalog key of a loaded LM Studio instance.

    LM Studio appends ``:2`` when the same model is loaded twice. ``gemma`` and
    ``gemma-qat`` stay different: only a trailing colon and digits are removed.
    """
    text = (model_id or "").strip()
    if ":" not in text:
        return text
    base, _, suffix = text.rpartition(":")
    if base and suffix.isdigit():
        return base
    return text
