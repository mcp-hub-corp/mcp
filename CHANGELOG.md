# Changelog

All notable changes to `mcp-hub-security` are documented here.
Newest entry first.

## [Unreleased] — 2026-05-16

### Fixed

- **BUG-W3-001 (P1, fail-OPEN bypass in cached mode)** — when
  `MCPHUB_FAIL_MODE=cached` and the caller does not pass `content_sha256`,
  the guard `if mode == "cached" and content_sha256:` silently dropped into
  the default `open` tail, exiting 0 (allow) instead of blocking. Security
  model bypass: a malformed call could bypass cached-mode enforcement.
  Fix: cached mode without a content hash now fail-CLOSEDs (exit 2). Removed
  `@pytest.mark.xfail(strict=True)` from
  `tests/test_fail_mode_edge.py::test_cached_mode_without_content_sha_falls_through_to_closed`.

### Added

- **Wire-contract schema validation** (`mcp_hub_security/validators.py`):
  every API response is now validated against
  `mcp_hub_security/schemas/scan_result.schema.json` (Draft 2020-12). Unknown
  `risk_level` values, missing required fields, or non-object payloads are
  rejected before any policy decision (fail-CLOSED to `critical`).
- **`MCPHUB_FAIL_MODE` env var** (`mcp_hub_security/fail_mode.py`): controls
  what the watchdog does when the hub is unreachable or the response is
  malformed.
  - `open` (default, backward compatible) — emit warning, allow tool call
    (exit 0).
  - `closed` — emit error, block tool call (exit 2). Recommended for
    regulated / production deployments.
  - `cached` — look up SHA-256(content) in a local cache file
    (`$MCPHUB_CACHE_DIR`, default `~/.cache/mcp-hub-security/verdicts.json`)
    and reuse the previous verdict. Cache miss falls through to `closed`.
- **`MCPHUB_CERT_FINGERPRINT_SHA256` env var**: optional public-key pinning
  for the hub TLS leaf certificate. Defensive layer on top of standard CA
  validation; useful in high-assurance environments.
- New tests: `tests/test_validators.py` (13), `tests/test_fail_mode.py` (12),
  `tests/test_hub_contract.py` (4 — contract check between bundled schema
  and the hub's canonical copy).

### Changed

- **Bundled schema in wheel**: the `scan_result.schema.json` file is now
  shipped at `mcp_hub_security/schemas/` via
  `[tool.hatch.build.targets.wheel.force-include]` so the client never
  fetches it over the network.
- `mcp_hub_security.tools.mcp.check_mcp_safety` / `get_verdict` and
  `mcp_hub_security.tools.skill.check_skill_safety*` now pass
  `validate_schema=True` to `api_request`, so contract violations surface
  immediately as `RuntimeError("hub contract violation: …")`.
- `RISK_ORDER` policy already accepted `safe` (since v2.0.0); the
  `critical_blocked` decision now also treats `safe` as "block critical
  findings" (alignment with `none` / `low` semantics).
- `apply_mcp_policy` and `apply_skill_policy` consider `safe` an even
  stricter aliasing of `none` when deciding to flag critical findings.

### Fixed

- **B4-001** — Unknown `risk_level` no longer falls through to
  `RISK_ORDER.get(level, 99)` ambiguity; the watchdog now fails-CLOSED
  (treats unknown values as `critical`) before policy evaluation.
- **M4-002** — Hub asymmetry between `risk_level="none"` (legacy MCP path)
  and `risk_level="safe"` (SkillScan) resolved: client refuses `"none"` and
  hub now emits `"safe"` for perfect scores. The watchdog refuses any value
  outside the canonical enum (`safe|low|medium|high|critical`).
- **M4-023** — `mcp_hub_security/hooks/skill_watchdog.py:147-151`
  catch-all `sys.exit(0)` replaced with the configurable fail-mode helper
  so high-trust deployments can block on hub failure instead of silently
  allowing.

### Security

- **M3-062** — Draft 2020-12 wire contract published as
  `scan_result.schema.json`. Schema drift between hub and client now fails
  CI via `tests/test_hub_contract.py` (cross-repo comparison) before
  reaching customers.
- **M4-019** — HTTPS requests now use an explicit
  `ssl.create_default_context()` (no implicit disable path) and gain
  optional fingerprint pinning via `MCPHUB_CERT_FINGERPRINT_SHA256`.

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
