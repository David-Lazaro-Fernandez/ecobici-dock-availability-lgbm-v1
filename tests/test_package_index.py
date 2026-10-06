"""Every locked package must come from PyPI (see .claude/rules/package-index.md)."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]
PYPI = "https://pypi.org/simple"


def test_pyproject_pins_pypi_as_only_index():
    indexes = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["uv"]["index"]
    assert indexes == [{"name": "pypi", "url": PYPI, "default": True}]


def test_lockfile_resolves_only_from_pypi():
    lock = (ROOT / "uv.lock").read_text()
    registries = set(re.findall(r'registry = "([^"]+)"', lock))
    assert registries == {PYPI}
    assert "shadowbox" not in lock
