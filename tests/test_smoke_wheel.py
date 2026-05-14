"""Smoke test: build the wheel, install it in an isolated venv, run the entry point.

This is the test that would have caught the production outage. Pre-fix, the
console script `mcp-hub-security` raised `ModuleNotFoundError: No module
named 'server'` because the wheel pruned `server.py` AND the entry point
referenced the flat module name.

Skipped when:
  - `uv` is not on PATH (CI is expected to install uv)
  - The dist/ directory has no wheel for the current version (run `uv build` first)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"


def _find_wheel() -> Path | None:
    wheels = sorted(DIST_DIR.glob("mcp_hub_security-*.whl"))
    return wheels[-1] if wheels else None


def _have_uv() -> bool:
    return shutil.which("uv") is not None


@pytest.fixture(scope="module")
def installed_venv(tmp_path_factory):
    if not _have_uv():
        pytest.skip("uv not on PATH")
    wheel = _find_wheel()
    if wheel is None:
        pytest.skip(
            "No wheel in dist/. Run `uv build` before running smoke tests."
        )

    venv_dir = tmp_path_factory.mktemp("smoke-venv")
    # Recreate the venv directory cleanly.
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    subprocess.run(
        ["uv", "venv", str(venv_dir), "--python", f"{sys.version_info.major}.{sys.version_info.minor}"],
        check=True,
        capture_output=True,
    )
    env = {**os.environ, "VIRTUAL_ENV": str(venv_dir)}
    subprocess.run(
        ["uv", "pip", "install", str(wheel)],
        check=True,
        capture_output=True,
        env=env,
    )
    return venv_dir


def test_entry_point_is_installed(installed_venv):
    entry = installed_venv / "bin" / "mcp-hub-security"
    assert entry.exists(), f"Entry point script missing: {entry}"
    assert os.access(entry, os.X_OK)


def test_entry_point_runs_without_modulenotfounderror(installed_venv):
    """The headline regression: process must boot FastMCP, no import failures."""
    entry = installed_venv / "bin" / "mcp-hub-security"

    proc = subprocess.run(
        [str(entry)],
        input=b"",
        env={**os.environ, "MCPHUB_API_KEY": "test"},
        capture_output=True,
        timeout=5,
    )

    combined = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")

    # The exact customer-facing error string from the outage.
    assert "ModuleNotFoundError" not in combined, (
        f"Entry point raised ModuleNotFoundError:\n{combined}"
    )
    assert "No module named 'server'" not in combined
    assert "No module named 'config'" not in combined
    assert "No module named 'http_client'" not in combined
    assert "No module named 'policy'" not in combined


def test_watchdog_entry_point_installed(installed_venv):
    entry = installed_venv / "bin" / "mcp-hub-skill-watchdog"
    assert entry.exists(), f"Watchdog entry point script missing: {entry}"
