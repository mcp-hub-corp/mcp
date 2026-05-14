from __future__ import annotations
import os

import pytest


_MCPHUB_ENV_VARS = (
    "MCPHUB_API_KEY",
    "MCPHUB_API_URL",
    "MCPHUB_MIN_SCORE",
    "MCPHUB_MAX_RISK",
    "MCPHUB_DENIED_CAPABILITIES",
    "MCPHUB_POLL_INTERVAL",
    "MCPHUB_POLL_TIMEOUT",
    "MCPHUB_SKILL_MIN_SCORE",
    "MCPHUB_SKILL_MAX_RISK",
)


@pytest.fixture(autouse=True)
def _clean_mcphub_env(monkeypatch):
    """Strip every MCPHUB_* env var inherited from the host before each test.

    Without this, a developer who has `MCPHUB_API_KEY` exported in their shell
    silently changes test behavior (especially `importlib.reload(wdog)` style
    watchdog tests). Each test that needs an env var sets it explicitly.
    """
    for name in _MCPHUB_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # Also strip anything else with the MCPHUB_ prefix the caller might rely on.
    for name in list(os.environ):
        if name.startswith("MCPHUB_") and name not in _MCPHUB_ENV_VARS:
            monkeypatch.delenv(name, raising=False)
    yield
