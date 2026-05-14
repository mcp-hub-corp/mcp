from __future__ import annotations
import os
from dataclasses import dataclass


# Risk levels accepted by the SkillScan / MCP scan APIs. The watchdog and
# server share this set when validating MCPHUB_*_MAX_RISK at startup.
ALLOWED_RISK_LEVELS: tuple[str, ...] = ("safe", "none", "low", "medium", "high", "critical")

DEFAULT_API_URL = "https://api.mcp-hub.info/api/v1"


class ConfigError(ValueError):
    """Raised when an MCPHUB_* environment variable holds an invalid value."""


@dataclass
class MCPConfig:
    api_key: str
    api_url: str
    min_score: int
    max_risk: str
    denied_capabilities: list[str]
    poll_interval: float
    poll_timeout: float


@dataclass
class SkillConfig:
    api_key: str
    api_url: str
    min_score: int
    max_risk: str


def _env_str(name: str, default: str) -> str:
    """Return env var with empty-string normalized to the default.

    `os.environ.get(key, default)` only returns `default` when the key is
    absent, not when it is set to "". Inline `""` values (a common
    copy-paste mistake) would otherwise silently disable defaults.
    """
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"{name} must be an integer, got {raw!r}"
        ) from exc


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(
            f"{name} must be a number, got {raw!r}"
        ) from exc


def _env_risk(name: str, default: str) -> str:
    value = _env_str(name, default).strip().lower()
    if value not in ALLOWED_RISK_LEVELS:
        allowed = ", ".join(ALLOWED_RISK_LEVELS)
        raise ConfigError(
            f"{name} must be one of: {allowed}; got {value!r}"
        )
    return value


def _env_api_url(default: str = DEFAULT_API_URL) -> str:
    url = _env_str("MCPHUB_API_URL", default).rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ConfigError(
            f"MCPHUB_API_URL must start with http:// or https://; got {url!r}"
        )
    return url


def get_mcp_config() -> MCPConfig:
    return MCPConfig(
        api_key=os.environ.get("MCPHUB_API_KEY", ""),
        api_url=_env_api_url(),
        min_score=_env_int("MCPHUB_MIN_SCORE", 80),
        max_risk=_env_risk("MCPHUB_MAX_RISK", "low"),
        denied_capabilities=[
            c.strip()
            for c in os.environ.get("MCPHUB_DENIED_CAPABILITIES", "").split(",")
            if c.strip()
        ],
        poll_interval=_env_float("MCPHUB_POLL_INTERVAL", 2.0),
        poll_timeout=_env_float("MCPHUB_POLL_TIMEOUT", 300.0),
    )


def get_skill_config() -> SkillConfig:
    return SkillConfig(
        api_key=os.environ.get("MCPHUB_API_KEY", ""),
        api_url=_env_api_url(),
        min_score=_env_int("MCPHUB_SKILL_MIN_SCORE", 70),
        max_risk=_env_risk("MCPHUB_SKILL_MAX_RISK", "medium"),
    )
