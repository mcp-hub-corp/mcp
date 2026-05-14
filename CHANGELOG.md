# Changelog

All notable changes to `mcp-hub-security` are documented here.
Newest entry first.

## [2.0.1] — 2026-05-15

### Fixed (iter 2 — QA findings)

- **README path corrected**: `~/.claude/mcp.json` (does not exist) replaced
  with `~/.claude.json` so users following the global-config instructions
  land on the real Claude Code config file.
- **`.mcp.json` aligned with README snippet**: removed redundant
  `MCPHUB_MIN_SCORE` / `MCPHUB_MAX_RISK` env vars (defaults — README itself
  advises not to set them) and unified the placeholder to `YOUR_API_KEY`.
- **sdist no longer leaks `.quality-loop/`**: added
  `[tool.hatch.build.targets.sdist] exclude = [".quality-loop", ...]` to
  `pyproject.toml` and ignored the directory in `.gitignore`. Rebuild
  `dist/` to drop the 15 internal post-mortem markdown files that were
  shipping inside the source tarball.
- **LICENSE file added**: canonical MIT text with `Copyright (c) 2026 MCP
  Hub Corp`. The README MIT badge link now resolves; wheel METADATA picks
  up the license declaration.

### Fixed

- **Customer outage**: `uvx --from git+... mcp-hub-security` failed with
  `ModuleNotFoundError: No module named 'server'`. Three independent
  packaging bugs combined:
  - `[project.scripts]` referenced the flat module path `server:main` and
    `hooks.skill_watchdog:main`
  - `[tool.hatch.build.targets.wheel] packages = ["tools", "hooks"]`
    pruned `server.py`, `config.py`, `http_client.py` and `policy.py`
    from the wheel
  - `policy.py` and `tools/skill.py` still used flat
    `from config import ...` imports after the package rename
- **Watchdog blocked every clean skill**: `_RISK_ORDER` in the watchdog
  was missing the `"safe"` key. SkillScan returns `risk_level="safe"`
  for clean skills, which fell back to 99 and exceeded the default
  `MCPHUB_SKILL_MAX_RISK=medium`. Now imports `RISK_ORDER` from
  `mcp_hub_security.policy` so the two stay in sync.
- Empty-string env vars (`MCPHUB_API_URL=""`, etc.) now fall back to
  the documented default instead of becoming the active value.
- Invalid `MCPHUB_MIN_SCORE` / `MCPHUB_POLL_INTERVAL` / etc. now raise
  a clear `ConfigError` at startup instead of crashing on first tool
  call with a generic `ValueError`.
- `MCPHUB_MAX_RISK` and `MCPHUB_SKILL_MAX_RISK` are validated against
  the allowed risk-level set at startup.
- `MCPHUB_API_URL` is validated to start with `http://` or `https://`.

### Added

- `mcp-hub-security --version` — prints the version without paying the
  FastMCP import cost.
- `mcp-hub-security --health` — prints every `MCPHUB_*` env var the
  server reads, validates them, and ends with `status: OK` or
  `status: UNHEALTHY`. Exit 0 healthy, exit 2 misconfigured. Ideal
  first-line diagnostic for the `--debug-file` workflow.
- Fail-fast on missing `MCPHUB_API_KEY` — single-line stderr message
  pointing at the dashboard, exit code 2. Captured by
  `claude --debug-file=…`.
- `tests/test_imports.py` — parametrized importlib over every public
  module. Catches the next surviving flat import before it ships.
- `tests/test_smoke_wheel.py` — builds the wheel, installs it in an
  isolated venv, runs the entry point, asserts no
  `ModuleNotFoundError`. The exact regression scenario the customer hit.
- `tests/test_mcp_handshake.py` — full MCP JSON-RPC `initialize` +
  `tools/list` against the installed binary; asserts all 7 tools are
  exposed.
- `tests/conftest.py` autouse fixture strips every `MCPHUB_*` env var
  from the host before each test (eliminates leakage in
  `importlib.reload(wdog)` style tests).
- README `## Troubleshooting` section with `--health` workflow,
  `--debug-file` recovery, `uv cache clean` recipe, and Claude Desktop
  log path.
- `.github/workflows/ci.yml` — matrix CI across Python 3.11, 3.12,
  3.13, 3.14. Builds the wheel, installs it, runs the full pytest
  suite including the smoke + handshake tests.

### Changed

- Package layout: all modules moved under `mcp_hub_security/`. Imports
  inside the package are now fully qualified.
- `pyproject.toml`:
  - `version` → `2.0.1`
  - `[project.scripts]` → `mcp_hub_security.server:main` and
    `mcp_hub_security.hooks.skill_watchdog:main`
  - `[tool.hatch.build.targets.wheel] packages` → `["mcp_hub_security"]`
  - `fastmcp>=2.0` → `fastmcp>=3.2,<4` (2.10.0 is uninstallable on
    current pydantic)
  - Drop `pytest pythonpath = ["."]` — no longer needed with the
    proper package layout, and it was masking the original bug.
- README: pin every `git+https://github.com/mcp-hub-corp/mcp.git` URL
  to `@v2.0.1`, replace the broken PyPI badge, drop the inaccurate
  "Zero dependencies" claim, move the watchdog `MCPHUB_API_KEY` out
  of the inline command into the hook `env` block.
- `.mcp.json`: switch from the dev-time `python server.py` invocation
  to the production `uvx --from git+...@v2.0.1` form.

### Removed

- `tests/conftest.py` no longer ships two unused fixtures
  (`mcp_verdict`, `skill_result`); every test file defined its own
  factory helpers anyway.

## [2.0.0] — 2026-05-12

### Added

- Initial public release of `mcp-hub-security` (modular v2 architecture).
- `mcp-hub-skill-watchdog` Claude Code PostToolUse hook.
- 7 MCP tools: `check_mcp_safety`, `get_verdict`, `get_scan_result`,
  `get_credit_balance`, `check_skill_safety`, `check_skill_safety_url`,
  `get_skill_scan`.

> **Note:** v2.0.0 shipped a broken wheel. See the 2.0.1 entry above
> for the postmortem. The 2.0.0 tag exists for archaeology only;
> no published artifact references it.
