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
