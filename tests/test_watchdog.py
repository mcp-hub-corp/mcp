from __future__ import annotations
import json
from io import StringIO
from unittest.mock import mock_open, patch

import mcp_hub_security.hooks.skill_watchdog as wdog


SKILL_CONTENT = """---
name: my-skill
description: A test skill.
---

Do something.
"""

NON_SKILL_CONTENT = """# Just a README

This is not a skill file.
"""

HOOK_WRITE = {"tool_name": "Write", "tool_input": {"file_path": "/path/to/my-skill.md"}}
HOOK_EDIT = {"tool_name": "Edit", "tool_input": {"file_path": "/path/to/my-skill.md"}}


def _run(hook_input, file_content, api_result, monkeypatch, extra_env=None):
    extra_env = extra_env or {}
    monkeypatch.setenv("MCPHUB_API_KEY", extra_env.get("MCPHUB_API_KEY", "test-key"))
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", extra_env.get("MCPHUB_SKILL_MIN_SCORE", "70"))
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", extra_env.get("MCPHUB_SKILL_MAX_RISK", "medium"))

    # Re-read module-level vars after env change
    import importlib
    importlib.reload(wdog)

    captured = []

    def fake_print(data, **_kw):
        captured.append(data)

    with patch("sys.stdin", StringIO(json.dumps(hook_input))), \
         patch("builtins.open", mock_open(read_data=file_content)), \
         patch("mcp_hub_security.hooks.skill_watchdog._api_scan", return_value=api_result), \
         patch("builtins.print", side_effect=fake_print):
        try:
            wdog.main()
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

    output = captured[0] if captured else "{}"
    return exit_code, json.loads(output)


def _safe(score=9.0, risk="low"):
    return {
        "schema_version": "2.0.0",
        "score": score,
        "risk_level": risk,
        "has_critical": False,
        "finding_count": 0,
        "scan_id": "x",
    }


def _critical():
    return {
        "schema_version": "2.0.0",
        "score": 3.0,
        "risk_level": "critical",
        "has_critical": True,
        "finding_count": 5,
        "scan_id": "y",
    }


def test_is_skill_detects_valid_frontmatter():
    assert wdog._is_skill(SKILL_CONTENT) is True


def test_is_skill_rejects_plain_markdown():
    assert wdog._is_skill(NON_SKILL_CONTENT) is False


def test_is_skill_requires_both_fields():
    assert wdog._is_skill("---\nname: x\n---\nno description") is False


def test_safe_skill_exits_zero(monkeypatch):
    code, resp = _run(HOOK_WRITE, SKILL_CONTENT, _safe(), monkeypatch)
    assert code == 0
    assert resp.get("type") == "info"


def test_non_skill_file_exits_zero(monkeypatch):
    code, _resp = _run(HOOK_WRITE, NON_SKILL_CONTENT, _safe(), monkeypatch)
    assert code == 0


def test_critical_skill_exits_one(monkeypatch):
    code, resp = _run(HOOK_WRITE, SKILL_CONTENT, _critical(), monkeypatch)
    assert code == 1
    assert resp.get("type") == "error"


def test_blocked_message_contains_skill_name(monkeypatch):
    _, resp = _run(HOOK_WRITE, SKILL_CONTENT, _critical(), monkeypatch)
    assert "my-skill" in resp.get("message", "")


def test_non_md_file_skipped(monkeypatch):
    hook = {"tool_name": "Write", "tool_input": {"file_path": "/path/to/server.py"}}
    code, _ = _run(hook, SKILL_CONTENT, _critical(), monkeypatch)
    assert code == 0


def test_edit_tool_also_triggers(monkeypatch):
    code, resp = _run(HOOK_EDIT, SKILL_CONTENT, _safe(), monkeypatch)
    assert code == 0
    assert resp.get("type") == "info"


def test_safe_risk_level_with_default_max_medium_exits_zero(monkeypatch):
    """Regression: watchdog must accept risk_level='safe' (SkillScan's best level).

    Before the fix, _RISK_ORDER was missing the "safe" key, so risk_level="safe"
    fell back to 99 and exceeded the default MCPHUB_SKILL_MAX_RISK=medium,
    blocking every clean skill with exit code 1.
    """
    api_result = {
        "schema_version": "2.0.0",
        "score": 10.0,
        "risk_level": "safe",
        "has_critical": False,
        "finding_count": 0,
        "scan_id": "safe-scan-001",
    }
    code, resp = _run(HOOK_WRITE, SKILL_CONTENT, api_result, monkeypatch)
    assert code == 0
    assert resp.get("type") == "info"


def test_unknown_risk_level_fails_closed(monkeypatch):
    """B4-001: an unknown ``risk_level`` value must fail-CLOSED (treat as critical).

    Schema validation rejects the payload before policy is evaluated, so the
    watchdog exits 2 (malformed response) instead of silently allowing.
    """
    bogus = {
        "schema_version": "2.0.0",
        "score": 10.0,
        "risk_level": "unknown",
        "has_critical": False,
        "finding_count": 0,
        "scan_id": "z",
    }
    code, resp = _run(HOOK_WRITE, SKILL_CONTENT, bogus, monkeypatch)
    assert code == 2
    assert resp.get("type") == "error"


def test_legacy_none_risk_level_rejected(monkeypatch):
    """M4-002: hub no longer emits "none"; watchdog must refuse it."""
    legacy = {
        "schema_version": "2.0.0",
        "score": 10.0,
        "risk_level": "none",
        "has_critical": False,
        "finding_count": 0,
        "scan_id": "z",
    }
    code, _ = _run(HOOK_WRITE, SKILL_CONTENT, legacy, monkeypatch)
    assert code == 2


def test_api_failure_fail_open_default(monkeypatch):
    """M4-023: default fail-mode is open → API exception exits 0 with warning."""
    monkeypatch.setenv("MCPHUB_API_KEY", "test-key")
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "70")
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", "medium")
    monkeypatch.delenv("MCPHUB_FAIL_MODE", raising=False)

    import importlib
    importlib.reload(wdog)

    captured = []
    with patch("sys.stdin", StringIO(json.dumps(HOOK_WRITE))), \
         patch("builtins.open", mock_open(read_data=SKILL_CONTENT)), \
         patch(
             "mcp_hub_security.hooks.skill_watchdog._api_scan",
             side_effect=ConnectionError("hub unreachable"),
         ), \
         patch("builtins.print", side_effect=lambda d, **_: captured.append(d)):
        try:
            wdog.main()
            code = 0
        except SystemExit as e:
            code = e.code

    assert code == 0
    msg = json.loads(captured[0])
    assert msg["type"] == "warning"


def test_api_failure_fail_closed(monkeypatch):
    """M4-023: MCPHUB_FAIL_MODE=closed → API exception exits 2."""
    monkeypatch.setenv("MCPHUB_API_KEY", "test-key")
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "70")
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", "medium")
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "closed")

    import importlib
    importlib.reload(wdog)

    with patch("sys.stdin", StringIO(json.dumps(HOOK_WRITE))), \
         patch("builtins.open", mock_open(read_data=SKILL_CONTENT)), \
         patch(
             "mcp_hub_security.hooks.skill_watchdog._api_scan",
             side_effect=ConnectionError("hub unreachable"),
         ), \
         patch("builtins.print"):
        try:
            wdog.main()
            code = 0
        except SystemExit as e:
            code = e.code

    assert code == 2


def test_no_api_key_exits_zero(monkeypatch):
    monkeypatch.delenv("MCPHUB_API_KEY", raising=False)
    monkeypatch.setenv("MCPHUB_SKILL_MIN_SCORE", "70")
    monkeypatch.setenv("MCPHUB_SKILL_MAX_RISK", "medium")
    import importlib
    importlib.reload(wdog)
    with patch("sys.stdin", StringIO(json.dumps(HOOK_WRITE))):
        try:
            wdog.main()
            code = 0
        except SystemExit as e:
            code = e.code
    assert code == 0
