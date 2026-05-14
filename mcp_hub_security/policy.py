from __future__ import annotations
from mcp_hub_security.config import MCPConfig, SkillConfig

RISK_ORDER: dict[str, int] = {"safe": 0, "none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def apply_mcp_policy(verdict: dict, cfg: MCPConfig) -> tuple[bool, list[str]]:
    """Return (allowed, blocked_reasons) for an MCP scan verdict."""
    blocked: list[str] = []

    score: int = verdict.get("security_score", 0)
    risk_level: str = verdict.get("risk_level", "critical")
    capabilities: list[str] = verdict.get("capabilities", [])
    critical_count: int = verdict.get("findings_summary", {}).get("critical", 0)

    if score < cfg.min_score:
        blocked.append(f"Score {score} is below minimum {cfg.min_score}")

    if RISK_ORDER.get(risk_level, 99) > RISK_ORDER.get(cfg.max_risk, 1):
        blocked.append(f"Risk level '{risk_level}' exceeds maximum '{cfg.max_risk}'")

    for cap in capabilities:
        if cap in cfg.denied_capabilities:
            blocked.append(f"Denied capability detected: {cap}")

    if critical_count > 0 and cfg.max_risk in ("none", "low"):
        if not any("critical" in r.lower() for r in blocked):
            blocked.append(f"{critical_count} critical finding(s) detected")

    return len(blocked) == 0, blocked


def apply_skill_policy(result: dict, cfg: SkillConfig) -> tuple[bool, list[str]]:
    """Return (allowed, blocked_reasons) for a Skill scan result.

    Converts result['score'] (0–10 scale) to 0–100 before comparing against min_score.
    """
    blocked: list[str] = []

    raw_score: float = result.get("score", 0.0)
    score_100: int = round(raw_score * 10)
    risk_level: str = result.get("risk_level", "critical")
    has_critical: bool = result.get("has_critical", False)

    if score_100 < cfg.min_score:
        blocked.append(f"Score {score_100} is below minimum {cfg.min_score}")

    if RISK_ORDER.get(risk_level, 99) > RISK_ORDER.get(cfg.max_risk, 1):
        blocked.append(f"Risk level '{risk_level}' exceeds maximum '{cfg.max_risk}'")

    if has_critical and cfg.max_risk in ("none", "low", "medium"):
        if not any("critical" in r.lower() for r in blocked):
            blocked.append("Critical security findings detected")

    return len(blocked) == 0, blocked
