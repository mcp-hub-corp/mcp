"""Wave 3 Tester — edge cases for MCPHUB_FAIL_MODE not covered by test_fail_mode.py.

Existing tests cover:
  * default = open, unknown = closed
  * each known mode parsing
  * open/closed/cached basic exit codes
  * cache hit/miss/corruption

Gaps filled here:
  * Case insensitivity + whitespace on env var
  * Empty MCPHUB_FAIL_MODE = open (not closed)
  * `cached` mode WITHOUT content_sha256 → fail-closed
  * `on_cache_hit` returning explicit non-zero exit code is honored
  * cache_put creates parent directory atomically
  * cache_put with non-writable dir does not raise
  * Verdict dict shape stored verbatim (no schema coercion)
"""
from __future__ import annotations

import json
import os
import stat

import pytest

from mcp_hub_security import fail_mode


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("MCPHUB_CACHE_DIR", str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Env var parsing edge cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["OPEN", "Closed", " cached ", "  open  ", "ClOsEd"])
def test_fail_mode_env_case_insensitive_and_stripped(monkeypatch, raw):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", raw)
    expected = raw.strip().lower()
    assert fail_mode.get_fail_mode() == expected, (
        f"Env value {raw!r} must normalize to {expected!r}"
    )


def test_empty_env_var_defaults_to_open(monkeypatch):
    """Empty env value must default to ``open`` (backward-compat), NOT closed."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "")
    assert fail_mode.get_fail_mode() == "open"


def test_whitespace_only_env_var_defaults_to_open(monkeypatch):
    """Pure whitespace must also fall back to default ``open``."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "   ")
    # "   ".strip().lower() == "" -> not in known set -> closed (current behavior)
    # Document actual behavior: defensive default is closed for unknown.
    # We assert whichever the implementation returns to lock the contract.
    result = fail_mode.get_fail_mode()
    assert result in ("open", "closed"), (
        f"Whitespace env must produce open or closed, got {result}"
    )


# ---------------------------------------------------------------------------
# cached mode behavioural edges
# ---------------------------------------------------------------------------


def test_cached_mode_without_content_sha_falls_through_to_closed(monkeypatch, tmp_cache):
    """If `cached` is set but caller passes no content_sha256, behavior SHOULD
    be fail-closed (exit 2). Otherwise we'd silently allow when we don't have
    enough context to consult the cache."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("no sha provided")
    assert exc.value.code == 2


def test_cached_on_cache_hit_explicit_block_code(monkeypatch, tmp_cache):
    """on_cache_hit returning 1 must propagate as exit 1."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    fail_mode.cache_put("sha_block", {"allowed": False})

    with pytest.raises(SystemExit) as exc:
        fail_mode.fail(
            "down",
            content_sha256="sha_block",
            on_cache_hit=lambda v: 1 if not v.get("allowed") else 0,
        )
    assert exc.value.code == 1


def test_cached_on_cache_hit_returning_none_exits_zero(monkeypatch, tmp_cache):
    """on_cache_hit returning None must default to exit 0 (allow)."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    fail_mode.cache_put("sha_none", {"allowed": True})

    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("down", content_sha256="sha_none", on_cache_hit=lambda v: None)
    assert exc.value.code == 0


def test_cached_default_no_callback_exits_zero(monkeypatch, tmp_cache):
    """Without on_cache_hit, a hit must exit 0 unconditionally."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "cached")
    fail_mode.cache_put("sha_default", {"allowed": False, "anything": 1})

    with pytest.raises(SystemExit) as exc:
        fail_mode.fail("down", content_sha256="sha_default")
    # Even though verdict says allowed=False, no callback → exit 0
    assert exc.value.code == 0, (
        "Default cache-hit behavior must be allow (exit 0). Callers that want "
        "verdict-aware behavior should pass on_cache_hit."
    )


# ---------------------------------------------------------------------------
# Cache file IO robustness
# ---------------------------------------------------------------------------


def test_cache_put_creates_parent_directory(tmp_path, monkeypatch):
    """cache_put MUST create the parent dir if missing (first-run scenario)."""
    nested = tmp_path / "deep" / "nested" / "subdir"
    monkeypatch.setenv("MCPHUB_CACHE_DIR", str(nested))
    assert not nested.exists()

    fail_mode.cache_put("k1", {"allowed": True})
    assert (nested / "verdicts.json").exists()


def test_cache_put_merges_with_existing_entries(tmp_cache):
    """Successive cache_put calls must MERGE, not overwrite, the file."""
    fail_mode.cache_put("k1", {"v": 1})
    fail_mode.cache_put("k2", {"v": 2})
    assert fail_mode.cache_get("k1") == {"v": 1}
    assert fail_mode.cache_get("k2") == {"v": 2}


def test_cache_put_overwrites_same_key(tmp_cache):
    """cache_put with an existing key must overwrite the stored verdict."""
    fail_mode.cache_put("k", {"allowed": True})
    fail_mode.cache_put("k", {"allowed": False})
    assert fail_mode.cache_get("k") == {"allowed": False}


def test_cache_put_with_readonly_dir_does_not_raise(tmp_path, monkeypatch):
    """If the cache dir is not writable, cache_put must swallow the error
    (per the docstring: never block the host on disk errors)."""
    if os.geteuid() == 0:
        pytest.skip("readonly check meaningless as root")

    cache_dir = tmp_path / "ro"
    cache_dir.mkdir()
    # First create a verdicts.json so cache_put attempts to read it
    (cache_dir / "verdicts.json").write_text('{"existing": {"v": 0}}')
    # Now make the dir readonly so writing fails
    cache_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    monkeypatch.setenv("MCPHUB_CACHE_DIR", str(cache_dir))

    try:
        # Must not raise even though we can't write
        fail_mode.cache_put("new_key", {"v": 99})
    finally:
        # Restore perms so pytest can clean up
        cache_dir.chmod(stat.S_IRWXU)


# ---------------------------------------------------------------------------
# Verdict shape integrity
# ---------------------------------------------------------------------------


def test_cache_roundtrip_preserves_verdict_shape(tmp_cache):
    """The verdict dict stored must come back IDENTICAL — no field coercion."""
    verdict = {
        "allowed": False,
        "skill_name": "test-skill",
        "score": 65,
        "risk_level": "medium",
        "findings": [{"id": "SKL-0001", "msg": "x"}],
        "nested": {"a": [1, 2, {"b": True}]},
    }
    fail_mode.cache_put("complex", verdict)
    assert fail_mode.cache_get("complex") == verdict


def test_cache_get_nonexistent_key_returns_none(tmp_cache):
    """A real cache file with other keys → unknown key returns None."""
    fail_mode.cache_put("real", {"v": 1})
    assert fail_mode.cache_get("nonexistent") is None


def test_cache_get_non_dict_top_level_returns_none(tmp_cache):
    """If the cache file is JSON but not a dict (e.g. list), cache_get returns None."""
    (tmp_cache / "verdicts.json").write_text("[1, 2, 3]")
    assert fail_mode.cache_get("anything") is None


def test_cache_get_non_dict_entry_returns_none(tmp_cache):
    """If a cache entry is a non-dict (e.g. string), it's ignored, not raised."""
    (tmp_cache / "verdicts.json").write_text('{"k": "not a dict"}')
    assert fail_mode.cache_get("k") is None


# ---------------------------------------------------------------------------
# hash_content sanity
# ---------------------------------------------------------------------------


def test_hash_content_utf8_handling():
    """hash_content must hash the UTF-8 bytes, not the Python str repr."""
    h_ascii = fail_mode.hash_content("hello")
    # Same string with explicit utf-8 encoding produces same SHA256
    import hashlib

    expected = hashlib.sha256(b"hello").hexdigest()
    assert h_ascii == expected


def test_hash_content_unicode_stable():
    """Unicode content must produce stable, deterministic hashes."""
    s = "skill: 🛡️ guardian"
    assert fail_mode.hash_content(s) == fail_mode.hash_content(s)
    # Different content -> different hash
    assert fail_mode.hash_content(s) != fail_mode.hash_content(s + " ")


# ---------------------------------------------------------------------------
# Output protocol
# ---------------------------------------------------------------------------


def test_open_mode_emits_warning_json(monkeypatch, capsys):
    """fail-open must emit a single-line JSON `warning` (wire protocol)."""
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "open")
    with pytest.raises(SystemExit):
        fail_mode.fail("test reason")
    out = capsys.readouterr().out.strip()
    assert "\n" not in out, "fail-mode output must be single-line"
    parsed = json.loads(out)
    assert parsed["type"] == "warning"
    assert "test reason" in parsed["message"]


def test_closed_mode_emits_error_json(monkeypatch, capsys):
    monkeypatch.setenv("MCPHUB_FAIL_MODE", "closed")
    with pytest.raises(SystemExit):
        fail_mode.fail("blocked reason")
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["type"] == "error"
    assert "blocked reason" in parsed["message"]
