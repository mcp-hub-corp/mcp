from __future__ import annotations
from typing import Any

from config import get_skill_config
from http_client import api_request
from policy import apply_skill_policy


def _build_skill_response(result: dict[str, Any], cfg) -> dict[str, Any]:
    allowed, blocked_reasons = apply_skill_policy(result, cfg)

    if allowed:
        reason = (
            f"Skill passes all security checks "
            f"(score={result.get('score')}, risk={result.get('risk_level')})."
        )
    else:
        reason = "Skill blocked by security policy: " + "; ".join(blocked_reasons)

    return {
        "allowed": allowed,
        "reason": reason,
        "blocked_by_policy": blocked_reasons,
        "score": result.get("score"),
        "risk_level": result.get("risk_level"),
        "finding_count": result.get("finding_count"),
        "has_critical": result.get("has_critical"),
        "findings": result.get("findings", []),
        "scan_id": result.get("scan_id"),
    }


def check_skill_safety(content: str, skill_name: str = "unnamed") -> dict[str, Any]:
    """Scan a Claude Code Skill (SKILL.md) provided as a string for security vulnerabilities.

    Analyses the skill against 17 analyzers covering 61 rules including instruction
    override, capability abuse, prompt injection hooks, and more.

    Automatically consumes 5 credits for new scans. Returns instantly for cached content.

    Args:
        content: Raw SKILL.md content (the full file text).
        skill_name: Human-readable name for the skill. Defaults to "unnamed".

    Returns:
        allowed (bool): Whether the skill passes current policy.
        reason (str): Human-readable explanation.
        blocked_by_policy (list[str]): Policy violations causing a block.
        score (float): Raw security score (0-10 scale from the scanner).
        risk_level (str): safe | low | medium | high | critical.
        finding_count (int): Total number of findings.
        has_critical (bool): Whether any critical findings were detected.
        findings (list[dict]): Full list of findings.
        scan_id (str): Scan identifier for follow-up queries.
    """
    cfg = get_skill_config()
    result = api_request(
        "POST", "/skill-scan/",
        {"content": content, "skill_name": skill_name, "enable_ml": False},
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
    return _build_skill_response(result, cfg)


def check_skill_safety_url(url: str, skill_name: str = "unnamed") -> dict[str, Any]:
    """Fetch a SKILL.md from a URL and scan it for security vulnerabilities.

    Args:
        url: URL pointing to raw SKILL.md content (e.g. a GitHub raw URL).
        skill_name: Human-readable name for the skill. Defaults to "unnamed".

    Returns:
        Same structure as check_skill_safety().
    """
    cfg = get_skill_config()
    result = api_request(
        "POST", "/skill-scan/url/",
        {"url": url, "skill_name": skill_name, "enable_ml": False},
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
    return _build_skill_response(result, cfg)


def get_skill_scan(scan_id: str) -> dict[str, Any]:
    """Retrieve a previous skill scan result by its UUID.

    Args:
        scan_id: Scan UUID returned by a previous check_skill_safety() call.
    """
    cfg = get_skill_config()
    return api_request(
        "GET", f"/skill-scan/{scan_id}/", None,
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
