#!/usr/bin/env python3
"""MCP Hub Security — FastMCP server.

Security gate for MCP servers and Claude Code Skills.

Usage:
    mcp-hub-security                 run the MCP stdio server
    mcp-hub-security --version       print the version and exit
    mcp-hub-security --health        print a config summary and exit

Environment variables:
    MCPHUB_API_KEY              (required) API token from mcp-hub.info dashboard
    MCPHUB_API_URL              (optional) default: https://api.mcp-hub.info/api/v1
    MCPHUB_MIN_SCORE            (optional) default: 80
    MCPHUB_MAX_RISK             (optional) default: low
    MCPHUB_DENIED_CAPABILITIES  (optional) comma-separated list of denied capabilities
    MCPHUB_POLL_INTERVAL        (optional) default: 2
    MCPHUB_POLL_TIMEOUT         (optional) default: 300
    MCPHUB_SKILL_MIN_SCORE      (optional) default: 70
    MCPHUB_SKILL_MAX_RISK       (optional) default: medium
"""
from __future__ import annotations

import os
import sys

from mcp_hub_security import __version__
from mcp_hub_security.config import (
    ConfigError,
    get_mcp_config,
    get_skill_config,
)


def _print_version() -> None:
    print(f"mcp-hub-security {__version__}")


def _print_health() -> int:
    """Print a config summary and return an exit code (0 healthy, 2 misconfigured)."""
    api_key = os.environ.get("MCPHUB_API_KEY", "")
    api_key_status = "set" if api_key else "MISSING"

    print(f"mcp-hub-security {__version__} — health check")
    print(f"  MCPHUB_API_KEY: {api_key_status}")
    try:
        mcp_cfg = get_mcp_config()
        print(f"  MCPHUB_API_URL: {mcp_cfg.api_url}")
        print(f"  MCPHUB_MIN_SCORE: {mcp_cfg.min_score}")
        print(f"  MCPHUB_MAX_RISK: {mcp_cfg.max_risk}")
        print(f"  MCPHUB_DENIED_CAPABILITIES: {mcp_cfg.denied_capabilities or '(none)'}")
        print(f"  MCPHUB_POLL_INTERVAL: {mcp_cfg.poll_interval}")
        print(f"  MCPHUB_POLL_TIMEOUT: {mcp_cfg.poll_timeout}")
        skill_cfg = get_skill_config()
        print(f"  MCPHUB_SKILL_MIN_SCORE: {skill_cfg.min_score}")
        print(f"  MCPHUB_SKILL_MAX_RISK: {skill_cfg.max_risk}")
    except ConfigError as exc:
        print(f"  config error: {exc}", file=sys.stderr)
        return 2

    if not api_key:
        print(
            "  status: UNHEALTHY — set MCPHUB_API_KEY "
            "(get one at https://mcp-hub.info/accounts/dashboard/)",
            file=sys.stderr,
        )
        return 2

    print("  status: OK")
    return 0


def _validate_startup_env() -> None:
    """Fail-fast on missing or invalid environment configuration.

    Writes a single human-readable error line to stderr and exits with
    code 2. This is captured by Claude Code when `--debug-file` is set.
    """
    if not os.environ.get("MCPHUB_API_KEY"):
        sys.stderr.write(
            "ERROR: MCPHUB_API_KEY is required. "
            "Get one at https://mcp-hub.info/accounts/dashboard/\n"
        )
        sys.exit(2)

    try:
        get_mcp_config()
        get_skill_config()
    except ConfigError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(2)


def _build_server():
    """Construct the FastMCP server with all 7 tools wired.

    Imported lazily so `--version` and `--health` do not pay the cost of
    importing FastMCP (which transitively pulls in pydantic, starlette,
    uvicorn, etc.).
    """
    from fastmcp import FastMCP

    from mcp_hub_security.tools.mcp import (
        check_mcp_safety,
        get_credit_balance,
        get_scan_result,
        get_verdict,
    )
    from mcp_hub_security.tools.skill import (
        check_skill_safety,
        check_skill_safety_url,
        get_skill_scan,
    )

    server = FastMCP(
        "MCP Hub Security",
        instructions=(
            "Security gate for MCP servers and Claude Code Skills. "
            "Use check_mcp_safety before running any MCP server. "
            "Use check_skill_safety or check_skill_safety_url before loading any Skill. "
            "Detects prompt injection, secret exposure, tool poisoning, capability abuse, "
            "and 14+ other vulnerability classes. Requires MCPHUB_API_KEY."
        ),
    )

    # MCP server tools
    server.tool()(check_mcp_safety)
    server.tool()(get_verdict)
    server.tool()(get_scan_result)
    server.tool()(get_credit_balance)

    # Skill tools
    server.tool()(check_skill_safety)
    server.tool()(check_skill_safety_url)
    server.tool()(get_skill_scan)

    return server


def main() -> None:
    argv = sys.argv[1:]
    if argv:
        if argv[0] in ("-V", "--version"):
            _print_version()
            return
        if argv[0] == "--health":
            sys.exit(_print_health())
        if argv[0] in ("-h", "--help"):
            print(__doc__)
            return

    _validate_startup_env()

    server = _build_server()
    server.run()


if __name__ == "__main__":
    main()
