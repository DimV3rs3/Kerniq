"""Per-user folders, path masking, quota, and the local model address."""

from pathlib import Path

import pytest

from Kerniq.server.homes import (
    admit_bytes,
    assert_users_root,
    bind_jail,
    display_path,
    local_model_candidates,
    lock_model_api,
    logical_path,
    quota_bytes,
    reset_jail,
    reset_quota,
    set_quota,
    user_home,
    users_root,
)


def test_two_users_cannot_see_each_other(tmp_path):
    core = {"users_root": str(tmp_path / "homes"), "user_quota_bytes": 64 * 1024 * 1024}
    one = user_home(tmp_path, "a" * 32, core)
    two = user_home(tmp_path, "b" * 32, core)
    assert one != two
    assert one.parent == two.parent == users_root(tmp_path, core)
    (two / "secret.txt").write_text("no", encoding="utf-8")
    token = bind_jail(one)
    try:
        inside = logical_path("/workspace/notes/a.txt", one)
        assert inside == (one / "notes" / "a.txt").resolve()
        assert display_path(inside) == "/workspace/notes/a.txt"
        assert display_path(one) == "/workspace"
        with pytest.raises(PermissionError):
            logical_path(str(two / "secret.txt"), one)
        with pytest.raises(PermissionError):
            logical_path("../" + two.name + "/secret.txt", one)
        with pytest.raises(PermissionError):
            logical_path("/etc/passwd", one)
    finally:
        reset_jail(token)


def test_symlink_cannot_leave_the_user_folder(tmp_path):
    core = {"users_root": str(tmp_path / "homes")}
    home = user_home(tmp_path, "user-one", core)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("hidden", encoding="utf-8")
    (home / "link").symlink_to(outside)
    with pytest.raises(PermissionError):
        logical_path("/workspace/link/secret.txt", home)
    with pytest.raises(PermissionError):
        logical_path("link/secret.txt", home)


def test_quota_blocks_a_write_that_would_overflow(tmp_path):
    folder = tmp_path / "home"
    folder.mkdir()
    (folder / "already.txt").write_bytes(b"x" * 100)
    token_j = bind_jail(folder)
    token_q = set_quota({"used": 100, "limit": 120, "near": True, "full": False})
    try:
        assert admit_bytes(10, 0) == ""
        reason = admit_bytes(50, 0)
        assert "full" in reason.lower()
    finally:
        reset_quota(token_q)
        reset_jail(token_j)


def test_users_root_refuses_the_disk_root(tmp_path):
    with pytest.raises(ValueError):
        assert_users_root("/")
    made = assert_users_root(str(tmp_path / "disk" / "kerniq-users"))
    assert made.is_dir()


def test_server_mode_keeps_the_saved_local_model_url():
    class Api:
        provider = "lm_studio"
        base_url = "http://192.168.3.100:1234"

    class Ui:
        api = Api()

    locked = lock_model_api(Ui(), {"model_base_url": "http://127.0.0.1:1234"})
    assert locked.api.base_url == "http://192.168.3.100:1234"

    class Empty:
        provider = "lm_studio"
        base_url = ""

    class EmptyUi:
        api = Empty()

    fallback = lock_model_api(EmptyUi(), {"model_base_url": "http://127.0.0.1:1234"})
    assert fallback.api.base_url == "http://127.0.0.1:1234"
    urls = local_model_candidates("http://192.168.3.100:1234", "http://127.0.0.1:1235")
    assert urls[0] == "http://192.168.3.100:1234"
    assert "http://127.0.0.1:1234" in urls
    assert "http://127.0.0.1:1235" in urls

    class Meta:
        provider = "lm_studio"
        base_url = "http://169.254.169.254/"

    class MetaUi:
        api = Meta()

    with pytest.raises(PermissionError):
        lock_model_api(MetaUi(), {})

    class Cloud:
        provider = "openai"
        base_url = "http://127.0.0.1:8080/v1"

    class CloudUi:
        api = Cloud()

    with pytest.raises(PermissionError):
        lock_model_api(CloudUi(), {})


def test_default_user_folders_live_in_the_project_workspace(tmp_path, monkeypatch):
    project = tmp_path / "Kerniq"
    (project / "plugins").mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    monkeypatch.setattr("Kerniq.devtools.paths.find_project_root", lambda start=None: project)
    folder = user_home(tmp_path / "state", "c" * 32, {})
    assert folder.parent == (project / "workspace").resolve()
    assert folder.is_dir()
    other = user_home(tmp_path / "state", "d" * 32, {})
    assert other.parent == folder.parent
    assert other != folder
    legacy = (tmp_path / "state").resolve() / "homes" / ("e" * 32)
    legacy.mkdir(parents=True)
    (legacy / "keep.txt").write_text("kept", encoding="utf-8")
    moved = user_home(tmp_path / "state", "e" * 32, {})
    assert (moved / "keep.txt").read_text(encoding="utf-8") == "kept"
    assert moved.parent == (project / "workspace").resolve()


def test_default_quota_is_eight_gigabytes():
    assert quota_bytes({}) == 8 * 1024 * 1024 * 1024


def test_download_file_and_folder_zip(tmp_path):
    import io
    import zipfile

    from Kerniq.server.transfer import build_download

    root = tmp_path / "home"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.txt").write_text("hello", encoding="utf-8")
    (root / ".kerniq-venv").mkdir()
    (root / ".kerniq-venv" / "skip.txt").write_text("no", encoding="utf-8")
    body, name, kind = build_download(root, root / "notes" / "a.txt")
    assert name == "a.txt" and kind == "application/octet-stream" and body == b"hello"
    packed, zip_name, zip_kind = build_download(root, root)
    assert zip_name == "workspace.zip" and zip_kind == "application/zip"
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        names = set(archive.namelist())
    assert "workspace/notes/a.txt" in names
    assert not any("kerniq-venv" in item for item in names)
