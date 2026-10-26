import os
from pathlib import Path

from Kerniq.sandbox.deps import imports_in_source, missing_specs, scan_tree
from Kerniq.sandbox.venv import _is_other_venv_bin, _python_runs, sandbox_python_path


def test_scan_reads_versions_and_skips_stdlib(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("httpx==0.28.1\n# comment\n-e .\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import os\nimport httpx\nimport yaml\nfrom PIL import Image\n",
        encoding="utf-8",
    )
    specs = scan_tree(tmp_path)
    assert "httpx==0.28.1" in specs
    assert "pyyaml" in specs
    assert "pillow" in specs
    assert not any(item == "os" or item.startswith("os") for item in specs)


def test_tkinter_is_not_sent_to_pip(tmp_path: Path):
    (tmp_path / "main.py").write_text(
        "def pick():\n    import tkinter as tk\n    from tkinter import filedialog\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("tkinter\nhttpx\n", encoding="utf-8")
    specs = scan_tree(tmp_path)
    assert not any("tkinter" in item.lower() for item in specs)
    assert "httpx" in specs


def test_imports_and_missing_keep_existing_packages():
    found = imports_in_source("import json\nimport requests\n")
    assert "json" in found
    assert "requests" in found
    assert missing_specs(["httpx==1.0", "pydantic", "plugin_web_ui"], {"httpx"}) == ["pydantic"]


def test_other_venv_is_hidden(tmp_path: Path):
    other = tmp_path / "venv"
    bindir = other / ("Scripts" if os.name == "nt" else "bin")
    bindir.mkdir(parents=True)
    (other / "pyvenv.cfg").write_text("home = /tmp\n", encoding="utf-8")
    sandbox = sandbox_python_path(tmp_path / "workspace").parent
    sandbox.mkdir(parents=True)
    assert _is_other_venv_bin(str(bindir), sandbox.resolve())
    assert not _is_other_venv_bin(str(sandbox), sandbox.resolve())


def test_missing_python_does_not_count_as_a_sandbox(tmp_path: Path):
    from Kerniq.sandbox.proc import hidden_kwargs

    flags = hidden_kwargs()
    assert flags == {} or "creationflags" in flags
    assert _python_runs(tmp_path / "missing-python") is False


def test_sandbox_pip_falls_back_to_the_host(tmp_path, monkeypatch):
    from Kerniq.sandbox import venv as mod

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))

        class Result:
            returncode = 1
            stdout = ""
            stderr = ""

        return Result()

    seen = {"n": 0}

    def has_pip(_python):
        seen["n"] += 1
        return seen["n"] >= 3

    monkeypatch.setattr(mod, "hidden_run", fake_run)
    monkeypatch.setattr(mod, "_has_pip", has_pip)
    monkeypatch.setattr(mod, "_venv_site", lambda _python: tmp_path / "site")
    python = tmp_path / "bin" / "python"
    python.parent.mkdir()
    mod._bootstrap_pip(python)
    joined = [" ".join(str(part) for part in cmd) for cmd in calls]
    assert any("ensurepip" in item for item in joined)
    assert any("--target" in item and item.endswith(" pip") for item in joined)
    assert (tmp_path / "site").is_dir()
