"""Record which pip packages Kerniq installed, so uninstall can leave the rest."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROTECTED = {"pip", "setuptools", "wheel", "pkg_resources"}


def package_name(line: str) -> str | None:
    text = (line or "").strip()
    if not text or text.startswith("#") or text.startswith("-e "):
        if text.startswith("-e "):
            return None
        return None
    if " @ " in text:
        text = text.split(" @ ", 1)[0].strip()
    elif "==" in text:
        text = text.split("==", 1)[0].strip()
    else:
        text = text.split()[0]
    return text or None


def names_from_freeze(text: str) -> list[str]:
    found: list[str] = []
    seen = set()
    for line in (text or "").splitlines():
        name = package_name(line)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(name)
    return found


def freeze(python: str) -> list[str]:
    result = subprocess.run(
        [python, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "pip freeze failed")
    return names_from_freeze(result.stdout)


def added_packages(before: list[str], after: list[str]) -> list[str]:
    prior = {name.lower() for name in before}
    extra = []
    for name in after:
        if name.lower() in prior or name.lower() in PROTECTED:
            continue
        extra.append(name)
    return extra


def load(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: env_manifest.py freeze|commit|remove-new", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "freeze":
        python = argv[2] if len(argv) > 2 else sys.executable
        print(json.dumps(freeze(python)))
        return 0
    if cmd == "commit":
        # commit <manifest> <python> <created_venv 0|1> <created_runtime 0|1> <before.json>
        manifest = Path(argv[2])
        python = argv[3]
        created_venv = argv[4] == "1"
        created_runtime = argv[5] == "1"
        before = json.loads(Path(argv[6]).read_text(encoding="utf-8"))
        after = freeze(python)
        save(manifest, {
            "version": 1,
            "created_venv": created_venv,
            "created_runtime": created_runtime,
            "python": python,
            "preexisting": list(before),
            "installed_by_kerniq": added_packages(list(before), after),
        })
        return 0
    if cmd == "remove-new":
        data = load(Path(argv[2]))
        for name in data.get("installed_by_kerniq") or []:
            if str(name).lower() not in PROTECTED:
                print(name)
        return 0
    print("unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
