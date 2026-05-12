from __future__ import annotations
from unittest.mock import patch
import pytest

from tools.mcp import check_mcp_safety, get_credit_balance, get_scan_result, get_verdict


@pytest.fixture(autouse=True)
def default_env(monkeypatch):
    monkeypatch.setenv("MCPHUB_API_KEY", "test-key")
    monkeypatch.setenv("MCPHUB_MIN_SCORE", "80")
    monkeypatch.setenv("MCPHUB_MAX_RISK", "low")
    monkeypatch.delenv("MCPHUB_DENIED_CAPABILITIES", raising=False)


def _verdict(score=90, risk="low", caps=None, findings=None):
    return {
        "security_score": score,
        "risk_level": risk,
        "capabilities": caps or [],
        "owasp_risks": [],
        "findings_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
        "findings": findings or [],
        "credits_consumed": 5,
        "credits_remaining": 275,
    }


class TestCheckMcpSafety:
    def test_happy_path_allowed(self):
        submit = {"check_token": "tok1"}
        status = {"status": "resolved", "scan_id": "scan-001"}
        verdict = _verdict(score=90, risk="low")

        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [submit, status, verdict]
            result = check_mcp_safety("https://github.com/org/repo")

        assert result["allowed"] is True
        assert result["security_score"] == 90
        assert result["scan_id"] == "scan-001"
        assert result["credits_consumed"] == 5

    def test_blocked_by_low_score(self):
        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [
                {"check_token": "t"},
                {"status": "resolved", "scan_id": "s"},
                _verdict(score=60),
            ]
            result = check_mcp_safety("https://github.com/org/repo")

        assert result["allowed"] is False
        assert any("60" in r for r in result["blocked_by_policy"])

    def test_blocked_by_high_risk(self):
        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [
                {"check_token": "t"},
                {"status": "resolved", "scan_id": "s"},
                _verdict(risk="high"),
            ]
            result = check_mcp_safety("https://github.com/org/repo")

        assert result["allowed"] is False

    def test_scan_error_status_raises(self):
        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [
                {"check_token": "t"},
                {"status": "error", "error": "repo not found"},
            ]
            with pytest.raises(RuntimeError, match="repo not found"):
                check_mcp_safety("https://github.com/org/repo")

    def test_poll_timeout_raises(self, monkeypatch):
        monkeypatch.setenv("MCPHUB_POLL_TIMEOUT", "0")
        with patch("tools.mcp.api_request", return_value={"check_token": "t"}):
            with pytest.raises(RuntimeError, match="timed out"):
                check_mcp_safety("https://github.com/org/repo")

    def test_denied_capability_blocked(self, monkeypatch):
        monkeypatch.setenv("MCPHUB_DENIED_CAPABILITIES", "file_write,process_exec")
        verdict = _verdict(score=90, caps=["file_write", "network_egress"])

        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [{"check_token": "t"}, {"status": "resolved", "scan_id": "s"}, verdict]
            result = check_mcp_safety("https://github.com/org/repo")

        assert result["allowed"] is False
        assert "file_write" in result["denied_capabilities_found"]
        assert "network_egress" not in result["denied_capabilities_found"]

    def test_critical_and_high_findings_extracted(self):
        findings = [
            {"severity": "critical", "title": "A", "rule_id": "G1"},
            {"severity": "high", "title": "B", "rule_id": "G2"},
            {"severity": "low", "title": "C", "rule_id": "G3"},
        ]
        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [
                {"check_token": "t"},
                {"status": "resolved", "scan_id": "s"},
                _verdict(score=40, risk="critical", findings=findings),
            ]
            result = check_mcp_safety("https://github.com/org/repo")

        assert len(result["critical_findings"]) == 1
        assert len(result["high_findings"]) == 1

    def test_check_token_from_redirect_url(self):
        submit = {"redirect_url": "/scans/checking/mytoken123/"}
        with patch("tools.mcp.api_request") as m, patch("tools.mcp.time.sleep"):
            m.side_effect = [submit, {"status": "resolved", "scan_id": "s"}, _verdict()]
            result = check_mcp_safety("https://github.com/org/repo")
        assert result["allowed"] is True


class TestGetVerdict:
    def test_happy_path(self):
        with patch("tools.mcp.api_request", return_value=_verdict()):
            result = get_verdict("scan-001")
        assert result["allowed"] is True
        assert result["scan_id"] == "scan-001"

    def test_blocked_verdict(self):
        with patch("tools.mcp.api_request", return_value=_verdict(score=50, risk="critical")):
            result = get_verdict("scan-002")
        assert result["allowed"] is False

    def test_returns_owasp_risks(self):
        v = _verdict()
        v["owasp_risks"] = ["LLM01", "LLM06"]
        with patch("tools.mcp.api_request", return_value=v):
            result = get_verdict("scan-003")
        assert result["owasp_risks"] == ["LLM01", "LLM06"]


class TestGetScanResult:
    def test_returns_raw_response(self):
        raw = {"security_score": 85, "findings": [{"id": "1"}]}
        with patch("tools.mcp.api_request", return_value=raw):
            result = get_scan_result("scan-001")
        assert result == raw


class TestGetCreditBalance:
    def test_returns_credits_and_email(self):
        with patch("tools.mcp.api_request", return_value={"credit_balance": 150, "email": "u@e.com"}):
            result = get_credit_balance()
        assert result["credits"] == 150
        assert result["email"] == "u@e.com"

    def test_missing_fields_default_to_zero_and_empty(self):
        with patch("tools.mcp.api_request", return_value={}):
            result = get_credit_balance()
        assert result["credits"] == 0
        assert result["email"] == ""
