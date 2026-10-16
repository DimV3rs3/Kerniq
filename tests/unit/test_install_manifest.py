import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[2] / "scripts" / "env_manifest.py"
_spec = importlib.util.spec_from_file_location("env_manifest", _path)
env_manifest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(env_manifest)


def test_freeze_names_ignore_versions_and_editable_paths():
    text = "\n".join([
        "httpx==0.28.1",
        "Kerniq @ file:///E:/Kerniq",
        "pip==25.0",
        "-e git+https://example.com/pkg",
        "",
    ])
    assert env_manifest.package_name("Kerniq @ file:///E:/Kerniq") == "Kerniq"
    assert env_manifest.names_from_freeze(text) == ["httpx", "Kerniq", "pip"]


def test_uninstall_keeps_packages_that_were_already_there():
    before = ["httpx", "pip", "pytest"]
    after = ["httpx", "pip", "pytest", "pydantic", "Kerniq", "setuptools"]
    assert env_manifest.added_packages(before, after) == ["pydantic", "Kerniq"]
