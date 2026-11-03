"""A session commit can be rolled back. Someone else's commit cannot."""

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def engine():
    path = ROOT / "plugins" / "git_session" / "engine.py"
    spec = importlib.util.spec_from_file_location("kerniq_git_session_engine_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(folder: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(folder), *args], check=True, capture_output=True, text=True)


def test_commit_and_rollback_file(tmp_path, monkeypatch):
    module = engine()
    store = tmp_path / "sessions.json"
    monkeypatch.setattr(module, "sessions_path", lambda: store)
    folder = tmp_path / "workspace"
    folder.mkdir()
    (folder / "note.txt").write_text("one")
    module.note_session_start(folder, "chat")
    (folder / "note.txt").write_text("two")
    (folder / "extra.txt").write_text("new")
    made = module.commit_session(folder, "chat")
    assert made["committed"] is True
    assert (folder / "note.txt").read_text() == "two"
    restored = module.rollback_file(folder, "note.txt")
    assert restored["ok"] is True
    assert (folder / "note.txt").read_text() == "one"
    whole = module.rollback_session(folder)
    assert whole["ok"] is True
    assert not (folder / "extra.txt").exists()


def test_foreign_commit_is_kept(tmp_path, monkeypatch):
    module = engine()
    store = tmp_path / "sessions.json"
    monkeypatch.setattr(module, "sessions_path", lambda: store)
    folder = tmp_path / "workspace"
    folder.mkdir()
    (folder / "note.txt").write_text("one")
    module.note_session_start(folder, "chat")
    (folder / "note.txt").write_text("two")
    module.commit_session(folder, "chat")
    (folder / "theirs.txt").write_text("mine")
    _git(folder, "add", "theirs.txt")
    _git(folder, "-c", "user.name=Someone", "-c", "user.email=someone@example.com", "commit", "-m", "their work")
    refused = module.rollback_session(folder)
    assert refused["ok"] is False
    assert (folder / "theirs.txt").is_file()
