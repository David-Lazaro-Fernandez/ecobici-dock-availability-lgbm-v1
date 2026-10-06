# Package index: always PyPI

All Python packages for this project come from **PyPI (`https://pypi.org/simple`)**. Never
resolve, lock or install from any other index or mirror, including the shadowbox
Socket Registry Firewall.

- `pyproject.toml` pins PyPI as the default index (`[[tool.uv.index]]`, `default = true`).
  Keep that block; don't add other indexes.
- This machine's user-level `~/.config/uv/uv.toml` and `~/.config/pip/pip.conf` point to
  shadowbox and are managed by IT. Don't edit or delete them. The project setting takes
  precedence for `uv`.
- After any `uv add`, `uv remove` or `uv lock`, check that every `registry =` line in
  `uv.lock` is `https://pypi.org/simple`. `tests/test_package_index.py` enforces this.
- Never commit a `uv.lock` that references another index. If one slips in, re-lock from
  PyPI. If it was already pushed, rewrite the affected commits.
- With `pip` directly, pass `--index-url https://pypi.org/simple`; the user-level
  `pip.conf` would otherwise send it to shadowbox.
