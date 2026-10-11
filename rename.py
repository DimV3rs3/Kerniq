#!/usr/bin/env python3
"""
Script to rename all references of the old project name `Kerniq` to the new one `Kerniq`.

The script performs the following steps:
1. Recursively walks through the repository root.
2. For each file with a relevant extension (.py, .md, .toml, .yml, .txt) it reads the content,
   replaces all occurrences of the old name (case‑sensitive) and writes back if any change
   was made.
3. Handles special files in the egg‑info directory (`top_level.txt`, `entry_points.txt`).
4. Renames the top‑level package directory from `src/Kerniq` to `src/Kerniq`.
5. Prints a summary of changes performed.

Run it from PowerShell:
    python rename_to_kerniq.py
"""
import os
import pathlib
from typing import List

OLD = "Kerniq"
NEW = "Kerniq"

# File extensions to process (text files)
EXTENSIONS = {'.py', '.md', '.toml', '.yml', '.yaml', '.txt'}

CHANGED_FILES: List[pathlib.Path] = []
REPLACED_COUNT = 0


def replace_in_file(path: pathlib.Path) -> None:
    global REPLACED_COUNT
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"[WARN] Skipping {path}: {e}")
        return
    if OLD not in text:
        return
    new_text = text.replace(OLD, NEW)
    # Special case: replace 'kerniq' with 'kerniq'
    new_text = new_text.replace('kerniq', 'kerniq')
    path.write_text(new_text, encoding='utf-8')
    CHANGED_FILES.append(path)
    REPLACED_COUNT += text.count(OLD) + text.count('kerniq')


def process_directory(root: pathlib.Path) -> None:
    for path in root.rglob('*'):
        if path.is_file() and path.suffix.lower() in EXTENSIONS:
            replace_in_file(path)

    # Handle egg-info special files
    egg_info = root / 'src' / f'{NEW}.egg-info'
    if egg_info.exists():
        top_level = egg_info / 'top_level.txt'
        if top_level.exists() and OLD in top_level.read_text(encoding='utf-8'):
            top_level.write_text(f"{NEW}\n", encoding='utf-8')
            CHANGED_FILES.append(top_level)

        entry_points = egg_info / 'entry_points.txt'
        if entry_points.exists():
            content = entry_points.read_text(encoding='utf-8')
            new_content = content.replace('kerniq', 'kerniq').replace(f'{OLD}.__main__:main', f'{NEW}.__main__:main')
            if new_content != content:
                entry_points.write_text(new_content, encoding='utf-8')
                CHANGED_FILES.append(entry_points)

    # Rename the package directory
    src_dir = root / 'src'
    old_pkg = src_dir / OLD
    new_pkg = src_dir / NEW
    if old_pkg.exists() and not new_pkg.exists():
        print(f"Renaming {old_pkg} -> {new_pkg}")
        old_pkg.rename(new_pkg)


if __name__ == "__main__":
    root = pathlib.Path.cwd()
    process_directory(root)
    print("\n--- Summary ---")
    print(f"Replaced {REPLACED_COUNT} occurrences.")
    if CHANGED_FILES:
        print("Modified files:")
        for f in CHANGED_FILES:
            print(f"  - {f}")
    else:
        print("No files modified.")

    # Optionally delete the script itself after running
    # os.remove(__file__)
