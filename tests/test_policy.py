from __future__ import annotations
import pytest
from config import MCPConfig, SkillConfig
from policy import RISK_ORDER, apply_mcp_policy, apply_skill_policy


@pytest.fixture
def strict_mcp_cfg():
    return MCPConfig(
        api_key="key", api_url="https://api.mcp-hub.info/api/v1",
        min_score=80, max_risk="low",
        denied_capabilities=["file_write", "process_exec"],
        poll_interval=2.0, poll_timeout=300.0,
    )


@pytest.fixture
def default_skill_cfg():
    return SkillConfig(
        api_key="key", api_url="https://api.mcp-hub.info/api/v1",
        min_score=70, max_risk="medium",
    )


@pytest.fixture
def clean_verdict():
    return {
        "security_score": 90,
        "risk_level": "low",
        "capabilities": [],
        "findings_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
    }


@pytest.fixture
def clean_skill():
    return {"score": 9.0, "risk_level": "low", "has_critical": False}


def test_risk_order_is_ascending():
    assert RISK_ORDER["none"] < RISK_ORDER["low"] < RISK_ORDER["medium"]
    assert RISK_ORDER["medium"] < RISK_ORDER["high"] < RISK_ORDER["critical"]


def test_mcp_clean_passes(strict_mcp_cfg, clean_verdict):
    allowed, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is True
    assert reasons == []


def test_mcp_score_at_threshold_passes(strict_mcp_cfg, clean_verdict):
    clean_verdict["security_score"] = 80
    allowed, _ = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is True


def test_mcp_score_below_threshold_blocked(strict_mcp_cfg, clean_verdict):
    clean_verdict["security_score"] = 79
    allowed, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is False
    assert any("79" in r for r in reasons)


def test_mcp_risk_at_max_passes(strict_mcp_cfg, clean_verdict):
    clean_verdict["risk_level"] = "low"
    allowed, _ = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is True


def test_mcp_risk_exceeds_max_blocked(strict_mcp_cfg, clean_verdict):
    clean_verdict["risk_level"] = "medium"
    allowed, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is False
    assert any("medium" in r for r in reasons)


def test_mcp_denied_capability_blocked(strict_mcp_cfg, clean_verdict):
    clean_verdict["capabilities"] = ["file_write"]
    allowed, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is False
    assert any("file_write" in r for r in reasons)


def test_mcp_non_denied_capability_allowed(strict_mcp_cfg, clean_verdict):
    clean_verdict["capabilities"] = ["network_egress"]
    allowed, _ = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is True


def test_mcp_multiple_denied_caps_each_reported(strict_mcp_cfg, clean_verdict):
    clean_verdict["capabilities"] = ["file_write", "process_exec", "network_egress"]
    _, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    denied_reasons = [r for r in reasons if "Denied capability" in r]
    assert len(denied_reasons) == 2


def test_mcp_critical_findings_blocked_when_max_risk_low(strict_mcp_cfg, clean_verdict):
    clean_verdict["findings_summary"]["critical"] = 3
    allowed, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert allowed is False
    assert any("critical" in r.lower() for r in reasons)


def test_mcp_critical_findings_allowed_when_max_risk_critical(clean_verdict):
    cfg = MCPConfig(
        api_key="k", api_url="u", min_score=0, max_risk="critical",
        denied_capabilities=[], poll_interval=2.0, poll_timeout=300.0,
    )
    clean_verdict["security_score"] = 50
    clean_verdict["risk_level"] = "critical"
    clean_verdict["findings_summary"]["critical"] = 5
    allowed, _ = apply_mcp_policy(clean_verdict, cfg)
    assert allowed is True


def test_mcp_multiple_violations_all_reported(strict_mcp_cfg, clean_verdict):
    clean_verdict["security_score"] = 50
    clean_verdict["risk_level"] = "high"
    clean_verdict["capabilities"] = ["file_write"]
    _, reasons = apply_mcp_policy(clean_verdict, strict_mcp_cfg)
    assert len(reasons) >= 3


def test_skill_clean_passes(default_skill_cfg, clean_skill):
    allowed, reasons = apply_skill_policy(clean_skill, default_skill_cfg)
    assert allowed is True
    assert reasons == []


def test_skill_score_at_threshold_passes(default_skill_cfg, clean_skill):
    clean_skill["score"] = 7.0
    allowed, _ = apply_skill_policy(clean_skill, default_skill_cfg)
    assert allowed is True


def test_skill_score_below_threshold_blocked(default_skill_cfg, clean_skill):
    clean_skill["score"] = 6.9
    allowed, reasons = apply_skill_policy(clean_skill, default_skill_cfg)
    assert allowed is False
    assert any("69" in r for r in reasons)


def test_skill_risk_exceeds_max_blocked(default_skill_cfg, clean_skill):
    clean_skill["risk_level"] = "high"
    allowed, reasons = apply_skill_policy(clean_skill, default_skill_cfg)
    assert allowed is False
    assert any("high" in r for r in reasons)


def test_skill_critical_blocked_with_medium_max(default_skill_cfg, clean_skill):
    clean_skill["has_critical"] = True
    allowed, reasons = apply_skill_policy(clean_skill, default_skill_cfg)
    assert allowed is False
    assert any("critical" in r.lower() for r in reasons)


def test_skill_critical_allowed_when_max_risk_critical(clean_skill):
    cfg = SkillConfig(api_key="k", api_url="u", min_score=0, max_risk="critical")
    clean_skill["has_critical"] = True
    clean_skill["risk_level"] = "critical"
    allowed, _ = apply_skill_policy(clean_skill, cfg)
    assert allowed is True
