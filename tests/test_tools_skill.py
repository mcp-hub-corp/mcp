from __future__ import annotations
from unittest.mock import patch
import pytest

from tools.skill import check_skill_safety, check_skill_safety_url, get_skill_scan


SKILL_MD = """---
name: test-skill
description: A test skill for unit tests.
---

Do something useful.
"""


@pytest.fixture(autouse=True)
def default_env(monkeypatch):
    monkeypatch.setenv("MCPHUB_API_KEY", "test-key")
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "70")
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", "medium")


def _result(score=9.0, risk="low", has_critical=False, finding_count=0):
    return {
        "scan_id": "aaaa-bbbb-cccc-dddd",
        "skill_name": "test-skill",
        "risk_level": risk,
        "score": score,
        "finding_count": finding_count,
        "has_critical": has_critical,
        "findings": [],
    }


class TestCheckSkillSafety:
    def test_happy_path_allowed(self):
        with patch("tools.skill.api_request", return_value=_result()):
            result = check_skill_safety(SKILL_MD)
        assert result["allowed"] is True
        assert result["score"] == 9.0
        assert result["scan_id"] == "aaaa-bbbb-cccc-dddd"

    def test_blocked_by_low_score(self):
        with patch("tools.skill.api_request", return_value=_result(score=6.5)):
            result = check_skill_safety(SKILL_MD)
        assert result["allowed"] is False
        assert any("65" in r for r in result["blocked_by_policy"])

    def test_blocked_by_high_risk(self):
        with patch("tools.skill.api_request", return_value=_result(risk="high")):
            result = check_skill_safety(SKILL_MD)
        assert result["allowed"] is False

    def test_blocked_by_critical_finding(self):
        with patch("tools.skill.api_request", return_value=_result(has_critical=True)):
            result = check_skill_safety(SKILL_MD)
        assert result["allowed"] is False

    def test_default_skill_name_sent_as_unnamed(self):
        captured = []
        def capture(method, path, body, *, api_key, api_url, **kw):
            captured.append(body)
            return _result()
        with patch("tools.skill.api_request", side_effect=capture):
            check_skill_safety(SKILL_MD)
        assert captured[0]["skill_name"] == "unnamed"

    def test_custom_skill_name_passed_through(self):
        captured = []
        def capture(method, path, body, *, api_key, api_url, **kw):
            captured.append(body)
            return _result()
        with patch("tools.skill.api_request", side_effect=capture):
            check_skill_safety(SKILL_MD, skill_name="my-skill")
        assert captured[0]["skill_name"] == "my-skill"

    def test_enable_ml_is_always_false(self):
        captured = []
        def capture(method, path, body, *, api_key, api_url, **kw):
            captured.append(body)
            return _result()
        with patch("tools.skill.api_request", side_effect=capture):
            check_skill_safety(SKILL_MD)
        assert captured[0]["enable_ml"] is False

    def test_api_error_propagates(self):
        with patch("tools.skill.api_request", side_effect=RuntimeError("API error 500: error")):
            with pytest.raises(RuntimeError, match="API error"):
                check_skill_safety(SKILL_MD)


class TestCheckSkillSafetyUrl:
    def test_happy_path(self):
        with patch("tools.skill.api_request", return_value=_result()):
            result = check_skill_safety_url("https://raw.githubusercontent.com/org/repo/main/skill.md")
        assert result["allowed"] is True

    def test_blocked_by_risk(self):
        with patch("tools.skill.api_request", return_value=_result(risk="critical")):
            result = check_skill_safety_url("https://raw.githubusercontent.com/org/repo/main/skill.md")
        assert result["allowed"] is False

    def test_url_sent_in_request_body(self):
        captured = []
        def capture(method, path, body, *, api_key, api_url, **kw):
            captured.append(body)
            return _result()
        with patch("tools.skill.api_request", side_effect=capture):
            check_skill_safety_url("https://example.com/skill.md", skill_name="remote")
        assert captured[0]["url"] == "https://example.com/skill.md"
        assert captured[0]["skill_name"] == "remote"

    def test_api_400_propagates(self):
        with patch("tools.skill.api_request", side_effect=RuntimeError("API error 400: URL not allowed")):
            with pytest.raises(RuntimeError, match="400"):
                check_skill_safety_url("https://example.com/skill.md")


class TestGetSkillScan:
    def test_returns_raw_api_response(self):
        raw = {"scan_id": "x", "score": 8.0, "findings": []}
        with patch("tools.skill.api_request", return_value=raw):
            result = get_skill_scan("skill-uuid-001")
        assert result == raw

    def test_calls_correct_path(self):
        captured = []
        def capture(method, path, body, *, api_key, api_url, **kw):
            captured.append(path)
            return {}
        with patch("tools.skill.api_request", side_effect=capture):
            get_skill_scan("my-uuid")
        assert captured[0] == "/skill-scan/my-uuid/"
