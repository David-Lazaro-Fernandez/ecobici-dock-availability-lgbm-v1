"""Every locked package must come from PyPI or npmjs (see .claude/rules/package-index.md)."""

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
PYPI = "https://pypi.org/simple"
NPM = "https://registry.npmjs.org/"


def test_pyproject_pins_pypi_as_only_index():
    indexes = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["index"]
    assert indexes == [{"name": "pypi", "url": PYPI, "default": True}]


def test_lockfile_resolves_only_from_pypi():
    lock = (ROOT / "uv.lock").read_text()
    registries = set(re.findall(r'registry = "([^"]+)"', lock))
    assert registries == {PYPI}
    assert "shadowbox" not in lock


def test_web_pins_npmjs():
    assert (ROOT / "web" / ".npmrc").read_text().strip() == f"registry={NPM}"


def test_web_lockfile_resolves_only_from_npmjs():
    packages = json.loads((ROOT / "web" / "package-lock.json").read_text())["packages"]
    resolved = [p["resolved"] for p in packages.values() if "resolved" in p]
    assert resolved
    assert all(url.startswith(NPM) for url in resolved)
