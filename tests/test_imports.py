"""Importability smoke test for every public module.

Would have detected the `from config import ...` (flat) import in
`mcp_hub_security/tools/skill.py` that survived the package rename and
broke production for the customer.
"""
from __future__ import annotations

import importlib

import pytest


PUBLIC_MODULES = [
    "mcp_hub_security",
    "mcp_hub_security.config",
    "mcp_hub_security.http_client",
    "mcp_hub_security.policy",
    "mcp_hub_security.server",
    "mcp_hub_security.tools",
    "mcp_hub_security.tools.mcp",
    "mcp_hub_security.tools.skill",
    "mcp_hub_security.hooks",
    "mcp_hub_security.hooks.skill_watchdog",
]


@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_module_is_importable(module_name: str) -> None:
    module = importlib.import_module(module_name)
    assert module is not None


def test_version_is_exposed() -> None:
    import mcp_hub_security

    assert mcp_hub_security.__version__ == "2.0.1"
