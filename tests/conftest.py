from __future__ import annotations
import pytest


@pytest.fixture
def mcp_verdict():
    return {
        "security_score": 90,
        "risk_level": "low",
        "capabilities": [],
        "owasp_risks": [],
        "findings_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
        "findings": [],
        "credits_consumed": 5,
        "credits_remaining": 275,
    }


@pytest.fixture
def skill_result():
    return {
        "scan_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "skill_name": "test-skill",
        "risk_level": "low",
        "score": 9.0,
        "finding_count": 0,
        "has_critical": False,
        "findings": [],
    }
