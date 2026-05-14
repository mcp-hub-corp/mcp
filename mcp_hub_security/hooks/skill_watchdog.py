#!/usr/bin/env python3
"""Skill watchdog — Claude Code PostToolUse hook.

Scans newly created or edited SKILL.md files for security vulnerabilities
and warns (or blocks) based on MCPHUB_SKILL_MIN_SCORE / MCPHUB_SKILL_MAX_RISK.

Install in ~/.claude/settings.json:

    {
      "hooks": {
        "PostToolUse": [{
          "matcher": "Write|Edit",
          "hooks": [{"type": "command",
                     "command": "python /path/to/hooks/skill_watchdog.py"}]
        }]
      }
    }
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request

from mcp_hub_security.policy import RISK_ORDER as _RISK_ORDER

_API_KEY = os.environ.get("MCPHUB_API_KEY", "")
_API_URL = os.environ.get("MCPHUB_API_URL", "https://api.mcp-hub.info/api/v1").rstrip("/")
_MIN_SCORE = int(os.environ.get("MCPHUB_SKILL_MIN_SCORE", "70"))
_MAX_RISK = os.environ.get("MCPHUB_SKILL_MAX_RISK", "medium")

_SKILL_RE = re.compile(
    r"^---\s*\n(?:[^\n]*\n)*?name:\s*\S[^\n]*\n(?:[^\n]*\n)*?description:\s*\S[^\n]*",
    re.MULTILINE,
)


def _is_skill(content: str) -> bool:
    return bool(_SKILL_RE.search(content))


def _api_scan(content: str, skill_name: str) -> dict:
    data = json.dumps({"content": content, "skill_name": skill_name, "enable_ml": False}).encode()
    req = urllib.request.Request(
        f"{_API_URL}/skill-scan/",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _emit(msg_type: str, message: str) -> None:
    print(json.dumps({"type": msg_type, "message": message}))


def main() -> None:
    if not _API_KEY:
        sys.exit(0)

    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path: str = hook_input.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".md"):
        sys.exit(0)

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        sys.exit(0)

    if not _is_skill(content):
        sys.exit(0)

    skill_name = os.path.splitext(os.path.basename(file_path))[0]

    try:
        result = _api_scan(content, skill_name)
    except Exception as exc:
        _emit("warning", f"MCP Hub: skill scan failed for '{skill_name}': {exc}")
        sys.exit(0)

    raw_score: float = result.get("score", 0.0)
    score_100: int = round(raw_score * 10)
    risk_level: str = result.get("risk_level", "unknown")
    has_critical: bool = result.get("has_critical", False)
    finding_count: int = result.get("finding_count", 0)
    scan_id: str = result.get("scan_id", "")

    score_too_low = score_100 < _MIN_SCORE
    risk_too_high = _RISK_ORDER.get(risk_level, 99) > _RISK_ORDER.get(_MAX_RISK, 2)
    critical_blocked = has_critical and _MAX_RISK in ("none", "low", "medium")

    if score_too_low or risk_too_high or critical_blocked:
        reasons: list[str] = []
        if score_too_low:
            reasons.append(f"score {score_100}/100 below minimum {_MIN_SCORE}")
        if risk_too_high:
            reasons.append(f"risk '{risk_level}' exceeds maximum '{_MAX_RISK}'")
        if critical_blocked:
            reasons.append("critical findings detected")

        message = (
            f"MCP Hub Security blocked skill '{skill_name}': "
            + "; ".join(reasons)
            + f". Score: {score_100}/100, Risk: {risk_level}, Findings: {finding_count}."
        )
        if scan_id:
            message += f" Review: https://mcp-hub.info/skill-scan/result/{scan_id}/"

        _emit("error", message)
        sys.exit(1)

    _emit(
        "info",
        f"MCP Hub: skill '{skill_name}' passed security check "
        f"(score={score_100}/100, risk={risk_level}, findings={finding_count}).",
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
