"""Build 2: paths stay at the project, homes can span disks, tokens stay capped."""

from pathlib import Path

import pytest

from Kerniq.core.runtime_flow import clamp_output_tokens
from Kerniq.devtools.paths import anchored_dir, pin_process_root
from Kerniq.server.debug import arm, request_unlocked, token_matches
from Kerniq.server.homes import user_home
from Kerniq.tools.packs.web.tools import _safe_download_name, downloads_dir


def test_settings_paths_stay_on_the_install_when_cwd_is_elsewhere(tmp_path, monkeypatch):
    pytest.importorskip("tomllib")
    install = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KERNIQ_ROOT", raising=False)
    monkeypatch.delenv("KERNIQ_HOME", raising=False)
    from Kerniq.settings.loader import SettingsProvider

    cfg = SettingsProvider().config
    assert cfg.storage.state_dir == (install / "state").resolve()
    assert cfg.storage.sessions_dir == (install / "sessions").resolve()
    assert cfg.application.workspace_root == (install / "workspace").resolve()
    assert cfg.logging.log_file == (install / "logs" / "platform.jsonl").resolve()


def test_launch_outside_the_install_still_uses_it(tmp_path, monkeypatch):
    install = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(tmp_path)
    # setenv records the previous value. pin_process_root overwrites it.
    # delenv on a missing variable does not, so the install path would leak.
    monkeypatch.setenv("KERNIQ_ROOT", "")
    monkeypatch.delenv("KERNIQ_HOME", raising=False)
    root = pin_process_root()
    assert root == install
    assert Path.cwd().resolve() == install
    state = anchored_dir("./state")
    assert state == (install / "state").resolve()
    assert state.is_absolute()


def test_pin_from_scripts_uses_the_project(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='k'\n", encoding="utf-8")
    (project / "plugins").mkdir()
    (project / "plugins" / "demo.txt").write_text("x", encoding="utf-8")
    monkeypatch.chdir(scripts)
    monkeypatch.delenv("KERNIQ_HOME", raising=False)
    monkeypatch.setenv("KERNIQ_ROOT", "")
    root = pin_process_root()
    assert root == project.resolve()
    assert Path.cwd().resolve() == project.resolve()
    assert anchored_dir("./state") == (project / "state").resolve()


def test_clamp_keeps_a_typed_cap_and_leaves_auto_unset():
    assert clamp_output_tokens(None, 8192) is None
    assert clamp_output_tokens(1000, 8192) == 1000
    assert clamp_output_tokens(90000, 8192) == 8192
    assert clamp_output_tokens(None, 0) is None
    assert clamp_output_tokens(400, 0) == 400


def test_existing_home_stays_on_its_disk(tmp_path):
    one = tmp_path / "disk-a"
    two = tmp_path / "disk-b"
    core = {"users_root": str(one), "users_roots": [str(two)]}
    (two / "alice").mkdir(parents=True)
    home = user_home(tmp_path / "state", "alice", core)
    assert home == (two / "alice").resolve()
    assert (home / "workspace").is_dir()
    fresh = user_home(tmp_path / "state", "bob", core)
    assert fresh.parent in {one.resolve(), two.resolve()}
    assert (fresh / "attachments").is_dir()


def test_debug_token_is_one_browser(tmp_path):
    row = arm(tmp_path, True)
    assert token_matches(tmp_path, row["token"])
    assert token_matches(tmp_path, "nope") is False

    class Headers(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    headers = Headers({"Cookie": "kerniq_debug=" + row["token"]})
    assert request_unlocked(headers, tmp_path)
    arm(tmp_path, False)
    assert request_unlocked(headers, tmp_path) is False


def test_download_name_stays_inside_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr("Kerniq.server.homes.jail_root", lambda: None)
    folder = downloads_dir(tmp_path)
    assert folder == (tmp_path / ".downloads").resolve()
    assert _safe_download_name("https://example.com/Kerniq-0.1.8.zip?raw=1") == "Kerniq-0.1.8.zip"
    assert "/" not in _safe_download_name("../../etc/passwd")
    assert _safe_download_name("https://example.com/") == "download.bin"
