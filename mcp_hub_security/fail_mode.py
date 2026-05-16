"""Watchdog fail-mode helper.

When the hub is unreachable, the response fails schema validation, or any
other unexpected error fires inside the watchdog hook, we need a single
configurable decision point: *do we let the tool call through (fail-OPEN),
block it (fail-CLOSED), or consult a local cache?*

Configured via the ``MCPHUB_FAIL_MODE`` environment variable:

* ``open`` (default, backward-compatible) -- emit a warning and ``sys.exit(0)``
  so the host (Claude Code) continues. Use in dev or low-trust orgs.
* ``closed`` -- emit an error and ``sys.exit(2)`` so the host blocks the tool
  call. Use in regulated/production deployments.
* ``cached`` -- look up SHA256(content) in a local cache file and reuse the
  last verdict for that exact skill. Cache miss falls through to ``closed``.

The cache lives at ``$MCPHUB_CACHE_DIR`` (defaults to
``~/.cache/mcp-hub-security/verdicts.json``) so it persists across runs but
stays per-user. Cached entries are pruned manually -- this is intentionally
simple; clients that need richer offline behavior should call the hub directly
from CI.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Literal

FailMode = Literal["open", "closed", "cached"]
CacheHitCallback = Callable[[dict[str, Any]], int | None]

_DEFAULT_CACHE_PATH = Path.home() / ".cache" / "mcp-hub-security" / "verdicts.json"


def get_fail_mode() -> FailMode:
    """Return the current fail-mode. Unknown values fail-CLOSED (defensive)."""
    raw = (os.environ.get("MCPHUB_FAIL_MODE") or "open").strip().lower()
    if raw in ("open", "closed", "cached"):
        return raw  # type: ignore[return-value]
    return "closed"


def _cache_path() -> Path:
    override = os.environ.get("MCPHUB_CACHE_DIR")
    if override:
        return Path(override) / "verdicts.json"
    return _DEFAULT_CACHE_PATH


def cache_get(content_sha256: str) -> dict | None:
    """Return cached verdict for the given content hash, or ``None``."""
    path = _cache_path()
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    entry = data.get(content_sha256)
    return entry if isinstance(entry, dict) else None


def cache_put(content_sha256: str, verdict: dict) -> None:
    """Persist a verdict for offline ``cached`` mode. Best-effort, never raises."""
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        data[content_sha256] = verdict
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        # Cache failures are non-fatal — never block the host on disk errors.
        return


def hash_content(content: str) -> str:
    """SHA-256 of UTF-8 content. Used as cache key for skills."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _emit(msg_type: str, message: str) -> None:
    """Single-line JSON emit (matches the watchdog wire protocol)."""
    print(json.dumps({"type": msg_type, "message": message}))


def fail(
    reason: str,
    *,
    content_sha256: str | None = None,
    on_cache_hit: CacheHitCallback | None = None,
) -> None:
    """Apply the configured fail policy. Always calls ``sys.exit``.

    * In ``cached`` mode, if ``content_sha256`` is provided and we have a
      cached verdict, ``on_cache_hit(verdict)`` runs and we exit with whatever
      code it returns (default 0). On miss we fall through to ``closed``.
    * In ``open`` we warn + exit 0 (backward-compatible default).
    * In ``closed`` we error + exit 2.
    """
    mode = get_fail_mode()

    if mode == "cached" and content_sha256:
        cached = cache_get(content_sha256)
        if cached is not None:
            _emit(
                "warning",
                f"MCP Hub Security: hub unreachable ({reason}); using cached verdict.",
            )
            if on_cache_hit is not None:
                code = on_cache_hit(cached) or 0
                sys.exit(code)
            sys.exit(0)
        # cache miss -> fall through to closed
        _emit(
            "error",
            f"MCP Hub Security: hub unreachable ({reason}) and no cached verdict; blocking.",
        )
        sys.exit(2)

    if mode == "closed":
        _emit("error", f"MCP Hub Security: {reason}; blocking (fail-closed mode).")
        sys.exit(2)

    # default: open
    _emit("warning", f"MCP Hub Security: {reason} (fail-open mode, allowing).")
    sys.exit(0)
