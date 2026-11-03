"""New space in a folder is what grew past the first measurement."""

import os
import time

from Kerniq.storage.folder_usage import account, is_private_path, parse_quota, private_root, purge_older_than


def test_baseline_ignores_files_already_there(tmp_path):
    folder = tmp_path / "workspace"
    folder.mkdir()
    (folder / "old.txt").write_text("hello")
    store = tmp_path / "usage.json"
    first = account(folder, store=store)
    assert first["used"] == 0
    assert first["baseline"] == first["current"] > 0
    (folder / "new.txt").write_text("added-by-kerniq")
    second = account(folder, store=store)
    assert second["used"] == len("added-by-kerniq")
    assert second["used"] > 0


def test_shrink_never_goes_negative(tmp_path):
    folder = tmp_path / "workspace"
    folder.mkdir()
    target = folder / "old.txt"
    target.write_text("hello world")
    store = tmp_path / "usage.json"
    account(folder, store=store)
    target.write_text("x")
    again = account(folder, store=store)
    assert again["used"] == 0
    assert again["baseline"] == again["current"]


def test_downloads_purge_removes_only_old_files(tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    old = folder / "old.txt"
    fresh = folder / "fresh.txt"
    old.write_text("gone")
    fresh.write_text("stay")
    os.utime(old, (time.time() - 40 * 86400, time.time() - 40 * 86400))
    assert purge_older_than(folder, 30) == 1
    assert not old.exists()
    assert fresh.read_text() == "stay"
    assert purge_older_than(folder, 0) == 0


def test_git_growth_counts_and_original_git_does_not(tmp_path):
    folder = tmp_path / "workspace"
    git = folder / ".git"
    git.mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n")
    store = tmp_path / "usage.json"
    first = account(folder, store=store)
    assert first["used"] == 0
    (git / "objects").mkdir()
    (git / "objects" / "aa").write_text("pack")
    second = account(folder, store=store)
    assert second["used"] == len("pack")


def test_private_bookkeeping_is_hidden():
    assert is_private_path(private_root() / "folder_usage.json")
    assert is_private_path(private_root() / "git_sessions.json")


def test_quota_units():
    assert parse_quota(4, "gb") == 4 * 1024 * 1024 * 1024
    assert parse_quota(8, "mb") == 8 * 1024 * 1024
    assert parse_quota("", "gb") == 4 * 1024 * 1024 * 1024
