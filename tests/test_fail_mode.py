"""Tests for mcp_hub_security.fail_mode (M4-023)."""
from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest

from mcp_hub_security import fail_mode


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPHUB_CACHE_DIR", str(tmp_path))
    return tmp_path


def test_default_fail_mode_is_open(monkeypatch):
    monkeypatch.delenv("MCPHUB_FAIL_MODE", raising=False)
    assert fail_mode.get_fail_mode() == "open"


def test_unknown_fail_mode_fails_closed(monkeypatch):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "yolo")
    assert fail_mode.get_fail_mode() == "closed"


@pytest.mark.parametrize("mode", ["open", "closed", "cached"])
def test_known_fail_modes(monkeypatch, mode):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", mode)
    assert fail_mode.get_fail_mode() == mode


def test_fail_open_exits_zero(monkeypatch, capsys):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "open")
    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("network down")
    assert exc.value.code == 0
    captured = capsys.readouterr()
    msg = json.loads(captured.out.strip())
    assert msg["type"] == "warning"
    assert "network down" in msg["message"]


def test_fail_closed_exits_two(monkeypatch, capsys):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "closed")
    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("network down")
    assert exc.value.code == 2
    captured = capsys.readouterr()
    msg = json.loads(captured.out.strip())
    assert msg["type"] == "error"


def test_fail_cached_hit(monkeypatch, tmp_cache, capsys):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    sha = "deadbeef"
    fail_mode.cache_put(sha, {"allowed": True, "skill_name": "x"})

    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("network down", content_sha256=sha)
    assert exc.value.code == 0


def test_fail_cached_block_verdict(monkeypatch, tmp_cache):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    sha = "deadbeef"
    fail_mode.cache_put(sha, {"allowed": False, "skill_name": "x"})

    def _on_hit(verdict):
        return 0 if verdict.get("allowed", False) else 1

    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("network down", content_sha256=sha, on_cache_hit=_on_hit)
    assert exc.value.code == 1


def test_fail_cached_miss_blocks(monkeypatch, tmp_cache, capsys):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("net down", content_sha256="missing")
    assert exc.value.code == 2  # cache miss -> fail-closed


def test_cache_get_missing_file_returns_none(tmp_cache):
    assert fail_mode.cache_get("anything") is None


def test_cache_put_then_get(tmp_cache):
    fail_mode.cache_put("abc", {"allowed": True})
    assert fail_mode.cache_get("abc") == {"allowed": True}


def test_cache_get_corrupted_returns_none(tmp_cache):
    cache_file = tmp_cache / "verdicts.json"
    cache_file.write_text("not json")
    assert fail_mode.cache_get("abc") is None


def test_hash_content_stable():
    assert fail_mode.hash_content("hello") == fail_mode.hash_content("hello")
    assert fail_mode.hash_content("a") != fail_mode.hash_content("b")
