"""MCP stdio handshake test.

Launches the `mcp-hub-security` entry point as a subprocess, performs an MCP
JSON-RPC `initialize` + `tools/list`, and asserts the server reports the
expected name and exposes all 7 tools.

This is the end-to-end test that the customer's Claude Code CLI is doing.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"

EXPECTED_TOOLS = {
    "check_mcp_safety",
    "get_verdict",
    "get_scan_result",
    "get_credit_balance",
    "check_skill_safety",
    "check_skill_safety_url",
    "get_skill_scan",
}


def _have_uv() -> bool:
    return shutil.which("uv") is not None


def _find_wheel() -> Path | None:
    wheels = sorted(DIST_DIR.glob("mcp_hub_security-*.whl"))
    return wheels[-1] if wheels else None


@pytest.fixture(scope="module")
def installed_entry(tmp_path_factory):
    if not _have_uv():
        pytest.skip("uv not on PATH")
    wheel = _find_wheel()
    if wheel is None:
        pytest.skip("No wheel in dist/. Run `uv build` before running handshake tests.")

    venv_dir = tmp_path_factory.mktemp("handshake-venv")
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
    return venv_dir / "bin" / "mcp-hub-security"


def _send_jsonrpc(proc: subprocess.Popen, payload: dict) -> dict:
    assert proc.stdin is not None, "Popen was created with stdin=PIPE"
    assert proc.stdout is not None, "Popen was created with stdout=PIPE"
    proc.stdin.write((json.dumps(payload) + "\n").encode())
    proc.stdin.flush()
    # Read lines from stdout until we get a JSON object with matching id.
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout before responding")
        line = line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # FastMCP may emit non-JSON banner lines on stdout — skip.
            continue
        if msg.get("id") == payload.get("id"):
            return msg


def test_mcp_initialize_and_tools_list(installed_entry):
    proc = subprocess.Popen(
        [str(installed_entry)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPHUB_API_KEY": "test"},
    )
    try:
        # MCP initialize.
        init_resp = _send_jsonrpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0"},
                },
            },
        )
        assert init_resp.get("result"), f"initialize failed: {init_resp!r}"
        server_info = init_resp["result"].get("serverInfo", {})
        assert "MCP Hub Security" in server_info.get("name", ""), (
            f"unexpected serverInfo: {server_info!r}"
        )

        # Per MCP spec, send notifications/initialized before listing tools.
        assert proc.stdin is not None
        proc.stdin.write(
            (json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode()
        )
        proc.stdin.flush()

        tools_resp = _send_jsonrpc(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert tools_resp.get("result"), f"tools/list failed: {tools_resp!r}"
        tool_names = {t["name"] for t in tools_resp["result"].get("tools", [])}
        missing = EXPECTED_TOOLS - tool_names
        assert not missing, (
            f"missing tools: {missing}; got {tool_names}"
        )
        assert len(tool_names) == 7, f"expected exactly 7 tools, got {len(tool_names)}: {tool_names}"
    finally:
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
