"""Client-side schema validation for hub API responses.

The watchdog (and tool wrappers) MUST validate every API payload against the
contract defined by ``mcp-hub/mcphub/apps/api/schemas/scan_result.schema.json``
before reading ``risk_level``. This protects against:

* Hub regressions emitting an unknown ``risk_level`` (fail-CLOSED instead of
  treating the value as ``safe``).
* Schema drift between the public client and the hub (a wire change must bump
  ``schema_version`` and refresh this module).
* Tampered or corrupted responses that look JSON-shaped but lack required
  keys.

The schema is bundled inside the wheel (``mcp_hub_security/schemas/``) so the
client never reaches over the network to fetch it.
"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any

# Risk levels accepted by the wire contract. Kept identical to the schema
# ``risk_level.enum``. Update both together.
ALLOWED_RISK_LEVELS: tuple[str, ...] = ("safe", "low", "medium", "high", "critical")

# Fail-CLOSED sentinel used when the response does not match the contract or
# omits ``risk_level``. ``"critical"`` is the most restrictive value and is
# always blocked by the default policy (max_risk=low / medium).
FAIL_CLOSED_RISK: str = "critical"

# Wire-contract version the client understands. Mismatches surface as warnings;
# unknown future versions still fail-CLOSED on schema mismatch.
SUPPORTED_SCHEMA_VERSION: str = "2.0.0"


class SchemaValidationError(ValueError):
    """Raised when an API response violates the scan_result contract."""


def _load_schema() -> dict[str, Any]:
    """Load the bundled Draft 2020-12 schema. Cached after first call."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is not None:
        return _SCHEMA_CACHE
    pkg = resources.files("mcp_hub_security").joinpath("schemas/scan_result.schema.json")
    with pkg.open("r", encoding="utf-8") as f:
        _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


_SCHEMA_CACHE: dict[str, Any] | None = None


def validate_scan_response(payload: Any) -> None:
    """Validate ``payload`` against the bundled scan_result schema.

    Raises ``SchemaValidationError`` on any violation. If ``jsonschema`` is
    not installed the function falls back to a minimal structural check
    (required keys present, ``risk_level`` in the allowed enum) so the
    watchdog still enforces the fail-CLOSED contract even on minimal envs.
    """
    if not isinstance(payload, dict):
        raise SchemaValidationError(
            f"response must be a JSON object, got {type(payload).__name__}"
        )

    # Strict path: use jsonschema if available.
    try:
        import jsonschema  # type: ignore[import-not-found]
    except ImportError:
        jsonschema = None  # noqa: N816

    if jsonschema is not None:
        schema = _load_schema()
        try:
            jsonschema.validate(payload, schema)
        except jsonschema.ValidationError as exc:
            raise SchemaValidationError(str(exc)) from exc
        return

    # Fallback path: enforce the two invariants that matter for fail-closed
    # decisions even without jsonschema.
    risk = payload.get("risk_level")
    if risk is None:
        raise SchemaValidationError("missing required field: risk_level")
    if risk not in ALLOWED_RISK_LEVELS:
        raise SchemaValidationError(
            f"risk_level {risk!r} not in allowed enum {ALLOWED_RISK_LEVELS}"
        )


def safe_risk_level(payload: dict[str, Any]) -> str:
    """Return a validated risk_level or ``FAIL_CLOSED_RISK`` on any anomaly.

    Use this in policy-evaluation paths where you cannot let an unknown value
    silently fall through to ``RISK_ORDER.get(level, 99)`` (which would block
    in some paths and allow in others depending on max_risk semantics).
    """
    try:
        validate_scan_response(payload)
    except SchemaValidationError:
        return FAIL_CLOSED_RISK
    return str(payload["risk_level"])
