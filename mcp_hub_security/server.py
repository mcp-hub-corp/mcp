#!/usr/bin/env python3
"""MCP Hub Security — FastMCP server.

Security gate for MCP servers and Claude Code Skills.

Usage:
    python server.py

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

mcp = FastMCP(
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
mcp.tool()(check_mcp_safety)
mcp.tool()(get_verdict)
mcp.tool()(get_scan_result)
mcp.tool()(get_credit_balance)

# Skill tools
mcp.tool()(check_skill_safety)
mcp.tool()(check_skill_safety_url)
mcp.tool()(get_skill_scan)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
