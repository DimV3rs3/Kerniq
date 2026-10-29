"""Language packs. English stays in the shell. Other languages are JSON files.

A pack is:

    {
      "name_en": "Russian",
      "name_native": "Native name",
      "strings": { "Save": "Translation" }
    }

Keys in strings are the English text. Kerniq checks the file before it is
stored. A broken pack is refused. A pack that misses known interface
strings is stored, and the missing lines stay English.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


class PackError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(" ".join(self.errors))


def packs_dir(state_dir: Path | str) -> Path:
    return Path(state_dir) / "languages"


def bundled_dir() -> Path:
    return Path(__file__).resolve().parent / "languages"


def _slug(name: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return raw[:40] or "pack"


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _known_english() -> set[str]:
    bundled = _read(bundled_dir() / "ru.json") or {}
    strings = bundled.get("strings")
    if not isinstance(strings, dict):
        return set()
    return {key.strip() for key in strings if isinstance(key, str) and key.strip()}


def _plain(value: Any, *, limit: int, allow_newline: bool = False) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    allowed = "\n\t" if allow_newline else ""
    if any(ord(ch) < 32 and ch not in allowed for ch in text):
        return ""
    return text[:limit]


def validate_pack(data: Any) -> dict[str, Any]:
    """Return a clean pack, or raise PackError with every problem found."""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise PackError(["A language pack must be a JSON object."])
    name_en = _plain(data.get("name_en"), limit=80)
    name_native = _plain(data.get("name_native"), limit=80)
    strings = data.get("strings")
    if not name_en:
        errors.append("name_en is required and must be plain text.")
    if not name_native:
        errors.append("name_native is required and must be plain text.")
    if name_en.lower() == "english":
        errors.append("English is built in and cannot be imported.")
    if not isinstance(strings, dict):
        errors.append("strings must be an object of English text to translation.")
        strings = {}
    if isinstance(strings, dict) and len(strings) > 5000:
        errors.append("strings has more than 5000 entries.")
    clean: dict[str, str] = {}
    bad = 0
    if isinstance(strings, dict):
        for key, value in strings.items():
            if not isinstance(key, str) or not isinstance(value, str):
                bad += 1
                continue
            source = _plain(key, limit=400, allow_newline=True)
            target = _plain(value, limit=2000, allow_newline=True)
            if not source or not target:
                bad += 1
                continue
            clean[source] = target
    if bad:
        errors.append(f"{bad} translation(s) are empty or not text.")
    if isinstance(strings, dict) and not clean and not errors:
        errors.append("strings is empty.")
    if not clean and "strings is empty." not in errors and isinstance(strings, dict):
        errors.append("strings is empty.")
    unchanged = bool(clean) and all(key == value for key, value in clean.items())
    if unchanged and name_en and name_native.lower() == name_en.lower():
        errors.append("This pack does not translate anything. Every string is still English.")
    pack_id = _slug(str(data.get("id") or name_en or "pack"))
    if pack_id == "en":
        errors.append("English is built in and cannot be imported.")
    known = _known_english()
    covered = sorted(key for key in clean if key in known)
    missing = sorted(key for key in known if key not in clean)
    if known and clean and not covered:
        errors.append("This pack does not translate any known interface string.")
    if errors:
        raise PackError(errors)
    warnings: list[str] = []
    if missing:
        sample = ", ".join(missing[:6])
        more = "" if len(missing) <= 6 else f" (+{len(missing) - 6} more)"
        warnings.append(
            f"Partial pack: {len(covered)} of {len(known)} interface strings. "
            f"Missing stay in English: {sample}{more}."
        )
    return {
        "id": pack_id,
        "name_en": name_en,
        "name_native": name_native,
        "strings": clean,
        "warnings": warnings,
        "missing": missing,
    }


def ensure_seeded(state_dir: Path | str) -> None:
    """Copy bundled packs that are not already stored.

    An empty ``state/languages`` directory must not hide Russian. A pack the
    user already imported, including their own edit of ru.json, is left alone.
    """
    dest = packs_dir(state_dir)
    dest.mkdir(parents=True, exist_ok=True)
    source = bundled_dir()
    if not source.is_dir():
        return
    for path in source.glob("*.json"):
        target = dest / path.name
        if target.is_file():
            continue
        shutil.copy2(path, target)


def list_packs(state_dir: Path | str, *, with_strings: bool = False) -> list[dict[str, Any]]:
    ensure_seeded(state_dir)
    dest = packs_dir(state_dir)
    packs: list[dict[str, Any]] = []
    if not dest.is_dir():
        return packs
    for path in sorted(dest.glob("*.json")):
        raw = _read(path)
        if raw is None:
            packs.append({
                "id": path.stem,
                "name_en": path.stem,
                "name_native": "Invalid",
                "valid": False,
                "errors": ["File is not a JSON object."],
            })
            continue
        try:
            pack = validate_pack(raw)
        except PackError as exc:
            packs.append({
                "id": path.stem,
                "name_en": _plain(raw.get("name_en"), limit=80) or path.stem,
                "name_native": _plain(raw.get("name_native"), limit=80) or "Invalid",
                "valid": False,
                "errors": exc.errors,
            })
            continue
        pack["id"] = path.stem
        pack["valid"] = True
        if not with_strings:
            pack = {k: pack[k] for k in ("id", "name_en", "name_native", "valid")}
        packs.append(pack)
    return packs


def import_pack(state_dir: Path | str, data: Any) -> dict[str, Any]:
    ensure_seeded(state_dir)
    pack = validate_pack(data)
    warnings = list(pack.get("warnings") or [])
    missing = list(pack.get("missing") or [])
    stored = {
        "id": pack["id"],
        "name_en": pack["name_en"],
        "name_native": pack["name_native"],
        "strings": pack["strings"],
    }
    dest = packs_dir(state_dir)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{stored['id']}.json"
    path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "id": stored["id"],
        "name_en": stored["name_en"],
        "name_native": stored["name_native"],
        "warnings": warnings,
        "missing_count": len(missing),
    }


def delete_pack(state_dir: Path | str, pack_id: str) -> bool:
    ensure_seeded(state_dir)
    safe = _slug(pack_id)
    path = packs_dir(state_dir) / f"{safe}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True
