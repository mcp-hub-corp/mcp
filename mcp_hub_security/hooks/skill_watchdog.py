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
import urllib.request

from mcp_hub_security.config import (
    ALLOWED_RISK_LEVELS,
    DEFAULT_API_URL,
    ConfigError,
)
from mcp_hub_security.fail_mode import fail as _fail
from mcp_hub_security.fail_mode import hash_content as _hash_content
from mcp_hub_security.fail_mode import cache_put as _cache_put
from mcp_hub_security.policy import RISK_ORDER as _RISK_ORDER
from mcp_hub_security.validators import (
    FAIL_CLOSED_RISK,
    SchemaValidationError,
    validate_scan_response,
)


def _env(name: str, default: str) -> str:
    """Same semantics as config._env_str — empty-string falls back to default."""
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _load_env() -> None:
    """Read env vars into module-level state.

    Called once at module import and re-callable for tests that override
    env vars between cases.
    """
    global _API_KEY, _API_URL, _MIN_SCORE, _MAX_RISK
    _API_KEY = os.environ.get("MCPHUB_API_KEY", "")
    _API_URL = _env("MCPHUB_API_URL", DEFAULT_API_URL).rstrip("/")
    raw_min_score = _env("MCPHUB_SKILL_MIN_SCORE", "70")
    try:
        _MIN_SCORE = int(raw_min_score)
    except ValueError as exc:
        raise ConfigError(
            f"MCPHUB_SKILL_MIN_SCORE must be an integer, got {raw_min_score!r}"
        ) from exc
    _MAX_RISK = _env("MCPHUB_SKILL_MAX_RISK", "medium").strip().lower()
    if _MAX_RISK not in ALLOWED_RISK_LEVELS:
        allowed = ", ".join(ALLOWED_RISK_LEVELS)
        raise ConfigError(
            f"MCPHUB_SKILL_MAX_RISK must be one of: {allowed}; got {_MAX_RISK!r}"
        )


_API_KEY = ""
_API_URL = DEFAULT_API_URL
_MIN_SCORE = 70
_MAX_RISK = "medium"

try:
    _load_env()
except ConfigError:
    # Defer config errors to main() so `import mcp_hub_security.hooks.skill_watchdog`
    # never crashes (importability is a contract surfaced by tests/test_imports.py).
    pass

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
    # Re-read env in case the process was launched with vars set after the
    # initial import (rare, but tests rely on this behavior via reload).
    try:
        _load_env()
    except ConfigError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(2)

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
    content_sha = _hash_content(content)

    try:
        result = _api_scan(content, skill_name)
    except Exception as exc:
        # M4-023: route through configurable fail-mode (open/closed/cached)
        # instead of unconditionally exit(0). Backward-compatible default is
        # ``open`` so existing installs keep working.
        _fail(
            f"skill scan failed for '{skill_name}': {exc}",
            content_sha256=content_sha,
            on_cache_hit=lambda v: 0 if v.get("allowed", False) else 1,
        )
        return  # unreachable — _fail always exits

    # M3-062 + M4-002 + B4-001: validate against the wire contract. An
    # unknown/missing risk_level is treated as ``critical`` (most restrictive).
    try:
        validate_scan_response(result)
    except SchemaValidationError as exc:
        _emit(
            "error",
            f"MCP Hub Security: hub returned malformed response for '{skill_name}': {exc}",
        )
        sys.exit(2)

    raw_score: float = result.get("score", 0.0)
    score_100: int = round(raw_score * 10)
    # B4-001: any value outside the schema enum has already been rejected by
    # validate_scan_response, but we defensively re-check here so a future
    # schema relaxation cannot silently regress.
    risk_level: str = result.get("risk_level", FAIL_CLOSED_RISK)
    if risk_level not in ALLOWED_RISK_LEVELS:
        risk_level = FAIL_CLOSED_RISK
    has_critical: bool = result.get("has_critical", False)
    finding_count: int = result.get("finding_count", 0)
    scan_id: str = result.get("scan_id", "")

    score_too_low = score_100 < _MIN_SCORE
    risk_too_high = _RISK_ORDER.get(risk_level, _RISK_ORDER[FAIL_CLOSED_RISK]) > _RISK_ORDER.get(_MAX_RISK, 2)
    critical_blocked = has_critical and _MAX_RISK in ("safe", "none", "low", "medium")

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

        # Persist block-verdict for offline ``cached`` fail-mode.
        _cache_put(
            content_sha,
            {
                "allowed": False,
                "score_100": score_100,
                "risk_level": risk_level,
                "skill_name": skill_name,
            },
        )

        _emit("error", message)
        sys.exit(1)

    # Persist allow-verdict for offline ``cached`` fail-mode.
    _cache_put(
        content_sha,
        {
            "allowed": True,
            "score_100": score_100,
            "risk_level": risk_level,
            "skill_name": skill_name,
        },
    )

    _emit(
        "info",
        f"MCP Hub: skill '{skill_name}' passed security check "
        f"(score={score_100}/100, risk={risk_level}, findings={finding_count}).",
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
