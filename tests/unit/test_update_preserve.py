"""An in-place update must not delete user plugins, language packs, or settings."""

from __future__ import annotations

from Kerniq.devtools.update_check import overlay_release


def test_overlay_keeps_user_data_and_updates_kit(tmp_path):
    project = tmp_path / "Kerniq"
    (project / "plugins" / "web_ui" / "languages").mkdir(parents=True)
    (project / "plugins" / "my_tool").mkdir(parents=True)
    (project / "state").mkdir()
    (project / "workspace").mkdir()
    (project / "plugins" / "web_ui" / "languages" / "ru.json").write_text('{"old": true}', encoding="utf-8")
    (project / "plugins" / "web_ui" / "languages" / "mine.json").write_text('{"user": true}', encoding="utf-8")
    (project / "plugins" / "my_tool" / "main.py").write_text("print('user')\n", encoding="utf-8")
    (project / "state" / "settings.json").write_text('{"agent": {"workspace": "./workspace"}}', encoding="utf-8")
    (project / "src" / "Kerniq").mkdir(parents=True)
    (project / "src" / "Kerniq" / "__init__.py").write_text('__version__ = "0.1.7"\n', encoding="utf-8")

    release = tmp_path / "release"
    (release / "plugins" / "web_ui" / "languages").mkdir(parents=True)
    (release / "plugins" / "web_ui" / "languages" / "ru.json").write_text('{"old": false}', encoding="utf-8")
    (release / "src" / "Kerniq").mkdir(parents=True)
    (release / "src" / "Kerniq" / "__init__.py").write_text('__version__ = "0.1.8"\n', encoding="utf-8")
    (release / "state").mkdir()
    (release / "state" / "settings.json").write_text("{}", encoding="utf-8")

    overlay_release(release, project)

    assert (project / "src" / "Kerniq" / "__init__.py").read_text(encoding="utf-8") == '__version__ = "0.1.8"\n'
    assert '"user": true' in (project / "plugins" / "web_ui" / "languages" / "mine.json").read_text(encoding="utf-8")
    assert '"old": false' in (project / "plugins" / "web_ui" / "languages" / "ru.json").read_text(encoding="utf-8")
    assert "user" in (project / "plugins" / "my_tool" / "main.py").read_text(encoding="utf-8")
    assert "workspace" in (project / "state" / "settings.json").read_text(encoding="utf-8")
    assert (project / "workspace").is_dir()
