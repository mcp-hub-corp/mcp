"""Tests for mcp_hub_security.validators (M3-062, M4-002, B4-001)."""
from __future__ import annotations

import pytest

from mcp_hub_security.validators import (
    ALLOWED_RISK_LEVELS,
    FAIL_CLOSED_RISK,
    SUPPORTED_SCHEMA_VERSION,
    SchemaValidationError,
    safe_risk_level,
    validate_scan_response,
)


def _good_payload(**overrides):
    base = {
        "schema_version": "2.0.0",
        "scan_id": "01968c1e-4a2b-7000-8000-000000000001",
        "risk_level": "safe",
        "security_score": 100,
    }
    base.update(overrides)
    return base


def test_supported_schema_version_constant():
    assert SUPPORTED_SCHEMA_VERSION == "2.0.0"


def test_fail_closed_is_critical():
    # B4-001: fail-CLOSED sentinel must be the strictest level.
    assert FAIL_CLOSED_RISK == "critical"


def test_allowed_risk_levels_match_contract():
    # M4-002: the watchdog must NOT accept legacy "none".
    assert "none" not in ALLOWED_RISK_LEVELS
    assert set(ALLOWED_RISK_LEVELS) == {"safe", "low", "medium", "high", "critical"}


@pytest.mark.parametrize("level", ["safe", "low", "medium", "high", "critical"])
def test_valid_levels_pass_validation(level):
    validate_scan_response(_good_payload(risk_level=level))


def test_unknown_level_rejected():
    with pytest.raises(SchemaValidationError):
        validate_scan_response(_good_payload(risk_level="bogus"))


def test_legacy_none_rejected():
    # The hub no longer emits "none"; client must refuse it as a defensive
    # contract check.
    with pytest.raises(SchemaValidationError):
        validate_scan_response(_good_payload(risk_level="none"))


def test_missing_risk_level_rejected():
    payload = _good_payload()
    del payload["risk_level"]
    with pytest.raises(SchemaValidationError):
        validate_scan_response(payload)


def test_non_object_rejected():
    with pytest.raises(SchemaValidationError):
        validate_scan_response("not an object")  # type: ignore[arg-type]
    with pytest.raises(SchemaValidationError):
        validate_scan_response([1, 2, 3])  # type: ignore[arg-type]


def test_safe_risk_level_returns_canonical_on_valid():
    assert safe_risk_level(_good_payload(risk_level="medium")) == "medium"


def test_safe_risk_level_fails_closed_on_invalid():
    # B4-001: unknown -> "critical" so policy comparison always blocks.
    assert safe_risk_level(_good_payload(risk_level="weird")) == "critical"


def test_safe_risk_level_fails_closed_on_missing():
    payload = _good_payload()
    del payload["risk_level"]
    assert safe_risk_level(payload) == "critical"
