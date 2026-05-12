from __future__ import annotations
import os
from dataclasses import dataclass


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


def get_mcp_config() -> MCPConfig:
    return MCPConfig(
        api_key=os.environ.get("MCPHUB_API_KEY", ""),
        api_url=os.environ.get("MCPHUB_API_URL", "https://api.mcp-hub.info/api/v1").rstrip("/"),
        min_score=int(os.environ.get("MCPHUB_MIN_SCORE", "80")),
        max_risk=os.environ.get("MCPHUB_MAX_RISK", "low"),
        denied_capabilities=[
            c.strip()
            for c in os.environ.get("MCPHUB_DENIED_CAPABILITIES", "").split(",")
            if c.strip()
        ],
        poll_interval=float(os.environ.get("MCPHUB_POLL_INTERVAL", "2")),
        poll_timeout=float(os.environ.get("MCPHUB_POLL_TIMEOUT", "300")),
    )


def get_skill_config() -> SkillConfig:
    return SkillConfig(
        api_key=os.environ.get("MCPHUB_API_KEY", ""),
        api_url=os.environ.get("MCPHUB_API_URL", "https://api.mcp-hub.info/api/v1").rstrip("/"),
        min_score=int(os.environ.get("MCPHUB_SKILL_MIN_SCORE", "70")),
        max_risk=os.environ.get("MCPHUB_SKILL_MAX_RISK", "medium"),
    )
