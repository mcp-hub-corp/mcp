"""Contract test between hub API and watchdog client (M4-003).

Verifies that the schema bundled inside the public client
(``mcp_hub_security/schemas/scan_result.schema.json``) stays byte-identical
to the canonical copy in ``mcp-hub/mcphub/apps/api/schemas/``. If the hub
team changes the schema without refreshing the bundled copy, CI fails and
forces a sync.

If the hub repo is not present alongside the public client (e.g. CI of the
public repo running in isolation), the cross-repo check is skipped and we
only validate that the bundled schema is a well-formed Draft 2020-12 file.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest

from mcp_hub_security.validators import validate_scan_response


# Path to the hub repo's canonical schema, relative to the public client repo.
# In the monorepo this resolves to ``mcp-hub-platform/mcp-hub/...``. In the
# standalone public repo (``github.com/mcp-hub-corp/mcp``) the directory does
# not exist; we skip the cross-repo comparison there.
HUB_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "mcp-hub"
    / "mcphub"
    / "apps"
    / "api"
    / "schemas"
    / "scan_result.schema.json"
)


def _bundled_schema_path() -> Path:
    pkg = resources.files("mcp_hub_security").joinpath("schemas/scan_result.schema.json")
    return Path(str(pkg))


def test_bundled_schema_is_valid_json():
    """The schema shipped inside the wheel must parse and declare Draft 2020-12."""
    with _bundled_schema_path().open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert data.get("properties", {}).get("risk_level", {}).get("enum") == [
        "safe",
        "low",
        "medium",
        "high",
        "critical",
    ]


@pytest.mark.skipif(
    not HUB_SCHEMA_PATH.exists(),
    reason="hub repo not available alongside public client (standalone CI)",
)
def test_bundled_schema_matches_hub_canonical():
    """M4-003: bundled schema must equal the hub's canonical copy.

    Update procedure when this test fails:
      1. Hub team bumps schema in mcp-hub/mcphub/apps/api/schemas/.
      2. Refresh bundled copy:
         cp mcp-hub/mcphub/apps/api/schemas/scan_result.schema.json \\
            mcp-hub-mcp/mcp_hub_security/schemas/scan_result.schema.json
      3. Bump ``SUPPORTED_SCHEMA_VERSION`` in validators.py if the change
         is a breaking one.
    """
    with HUB_SCHEMA_PATH.open("r", encoding="utf-8") as f:
        hub = json.load(f)
    with _bundled_schema_path().open("r", encoding="utf-8") as f:
        bundled = json.load(f)
    assert hub == bundled, (
        "Bundled schema drifted from hub canonical. "
        "Re-copy the file and bump SUPPORTED_SCHEMA_VERSION if breaking."
    )


def test_realistic_verdict_payload_passes():
    """Smoke-validate a payload shaped like /api/v1/scans/{id}/verdict/."""
    payload = {
        "schema_version": "2.0.0",
        "scan_id": "01968c1e-4a2b-7000-8000-000000000001",
        "security_score": 92,
        "risk_level": "low",
        "safe": True,
        "capabilities": ["network_egress"],
        "owasp_risks": ["LLM01"],
        "findings_summary": {"critical": 0, "high": 0, "medium": 1, "low": 2, "total": 3},
        "findings": [
            {
                "id": "01968c1f-0000-7000-8000-000000000002",
                "severity": "medium",
                "title": "Insecure default",
                "description": "...",
                "file_path": "server.py",
                "line_number": 42,
                "vulnerability_class": "G013",
                "cwe_id": "CWE-1188",
                "remediation": "Set timeout explicitly.",
                "is_blurred": False,
            }
        ],
        "credits_consumed": 5,
        "credits_remaining": 95,
        "is_unlocked": True,
    }
    validate_scan_response(payload)


def test_realistic_skill_payload_passes():
    """Smoke-validate a payload shaped like /api/v1/skill-scan/."""
    payload = {
        "schema_version": "2.0.0",
        "scan_id": "01968c1e-4a2b-7000-8000-000000000003",
        "skill_name": "my-skill",
        "risk_level": "safe",
        "score": 10.0,
        "finding_count": 0,
        "has_critical": False,
        "findings": [],
    }
    validate_scan_response(payload)
