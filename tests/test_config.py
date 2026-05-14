from __future__ import annotations
import pytest
from mcp_hub_security.config import MCPConfig, SkillConfig, get_mcp_config, get_skill_config


def _clear(monkeypatch, *names):
    for n in names:
        monkeypatch.delenv(n, raising=False)


def test_mcp_config_defaults(monkeypatch):
    _clear(monkeypatch, "MCPHUB_API_KEY", "MCPHUB_API_URL", "MCPHUB_MIN_SCORE",
           "MCPHUB_MAX_RISK", "MCPHUB_DENIED_CAPABILITIES",
           "MCPHUB_POLL_INTERVAL", "MCPHUB_POLL_TIMEOUT")
    cfg = get_mcp_config()
    assert cfg.api_key == ""
    assert cfg.api_url == "https://api.mcp-hub.info/api/v1"
    assert cfg.min_score == 80
    assert cfg.max_risk == "low"
    assert cfg.denied_capabilities == []
    assert cfg.poll_interval == 2.0
    assert cfg.poll_timeout == 300.0


def test_mcp_config_from_env(monkeypatch):
    monkeypatch.setenv("MCPHUB_API_KEY", "my-key")
    monkeypatch.setenv("MCPHUB_MIN_SCORE", "60")
    monkeypatch.setenv("MCPHUB_MAX_RISK", "medium")
    monkeypatch.setenv("MCPHUB_DENIED_CAPABILITIES", "file_write, exec, network_egress")
    cfg = get_mcp_config()
    assert cfg.api_key == "my-key"
    assert cfg.min_score == 60
    assert cfg.max_risk == "medium"
    assert cfg.denied_capabilities == ["file_write", "exec", "network_egress"]


def test_mcp_config_api_url_strips_slash(monkeypatch):
    monkeypatch.setenv("MCPHUB_API_URL", "https://example.com/v1/")
    assert get_mcp_config().api_url == "https://example.com/v1"


def test_mcp_config_denied_empty_string(monkeypatch):
    monkeypatch.setenv("MCPHUB_DENIED_CAPABILITIES", "")
    assert get_mcp_config().denied_capabilities == []


def test_mcp_config_denied_single(monkeypatch):
    monkeypatch.setenv("MCPHUB_DENIED_CAPABILITIES", "file_write")
    assert get_mcp_config().denied_capabilities == ["file_write"]


def test_mcp_config_invalid_score_raises(monkeypatch):
    monkeypatch.setenv("MCPHUB_MIN_SCORE", "not_a_number")
    with pytest.raises(ValueError):
        get_mcp_config()


def test_skill_config_defaults(monkeypatch):
    _clear(monkeypatch, "MCPHUB_API_KEY", "MCPHUB_API_URL",
           "MCPHUB_SKILL_MIN_SCORE", "MCPHUB_SKILL_MAX_RISK")
    cfg = get_skill_config()
    assert cfg.api_key == ""
    assert cfg.api_url == "https://api.mcp-hub.info/api/v1"
    assert cfg.min_score == 70
    assert cfg.max_risk == "medium"


def test_skill_config_from_env(monkeypatch):
    monkeypatch.setenv("MCPHUB_API_KEY", "sk-key")
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "80")
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", "low")
    cfg = get_skill_config()
    assert cfg.api_key == "sk-key"
    assert cfg.min_score == 80
    assert cfg.max_risk == "low"


def test_skill_config_invalid_score_raises(monkeypatch):
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "bad")
    with pytest.raises(ValueError):
        get_skill_config()


def test_mcp_skill_independent_thresholds(monkeypatch):
    monkeypatch.setenv("MCPHUB_MIN_SCORE", "90")
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "55")
    assert get_mcp_config().min_score == 90
    assert get_skill_config().min_score == 55
