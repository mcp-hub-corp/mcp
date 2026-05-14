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
    return {"score": score, "risk_level": risk, "has_critical": False, "finding_count": 0, "scan_id": "x"}


def _critical():
    return {"score": 3.0, "risk_level": "critical", "has_critical": True, "finding_count": 5, "scan_id": "y"}


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
        "score": 10.0,
        "risk_level": "safe",
        "has_critical": False,
        "finding_count": 0,
        "scan_id": "safe-scan-001",
    }
    code, resp = _run(HOOK_WRITE, SKILL_CONTENT, api_result, monkeypatch)
    assert code == 0
    assert resp.get("type") == "info"


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
