from __future__ import annotations
import time
from typing import Any

from mcp_hub_security.config import get_mcp_config
from mcp_hub_security.http_client import api_request
from mcp_hub_security.policy import apply_mcp_policy


def _extract_check_token(resp: dict[str, Any]) -> str:
    token = resp.get("check_token") or resp.get("token")
    if token:
        return str(token)
    redirect = resp.get("redirect_url", "")
    parts = [p for p in redirect.split("/") if p]
    if len(parts) >= 2 and parts[-2] == "checking":
        return parts[-1]
    if parts:
        return parts[-1]
    raise RuntimeError(f"Cannot extract check_token from response: {resp}")


def _build_mcp_response(verdict: dict[str, Any], scan_id: str, cfg) -> dict[str, Any]:
    allowed, blocked_reasons = apply_mcp_policy(verdict, cfg)
    capabilities: list[str] = verdict.get("capabilities", [])
    denied_found = [c for c in capabilities if c in cfg.denied_capabilities]
    findings: list[dict[str, Any]] = verdict.get("findings", [])

    if allowed:
        reason = (
            f"MCP server passes all security checks "
            f"(score={verdict.get('security_score')}, risk={verdict.get('risk_level')})."
        )
    else:
        reason = "MCP server blocked by security policy: " + "; ".join(blocked_reasons)

    return {
        "allowed": allowed,
        "reason": reason,
        "security_score": verdict.get("security_score"),
        "risk_level": verdict.get("risk_level"),
        "blocked_by_policy": blocked_reasons,
        "capabilities": capabilities,
        "denied_capabilities_found": denied_found,
        "owasp_risks": verdict.get("owasp_risks", []),
        "findings_summary": verdict.get("findings_summary", {}),
        "critical_findings": [f for f in findings if f.get("severity") == "critical"],
        "high_findings": [f for f in findings if f.get("severity") == "high"],
        "credits_consumed": verdict.get("credits_consumed", 0),
        "credits_remaining": verdict.get("credits_remaining"),
        "scan_id": scan_id,
    }


def check_mcp_safety(url: str) -> dict[str, Any]:
    """Scan a Git repository for security vulnerabilities before running it as an MCP server.

    Performs a full security analysis against 14 vulnerability classes including
    prompt injection, secret exposure, tool poisoning, SSRF, and more.

    Automatically consumes 5 credits from your MCP Hub account for new scans.
    Returns instantly using a cached result if the repository was already scanned
    at the same commit.

    Args:
        url: Git repository URL (GitHub, GitLab, or Bitbucket).
             Example: https://github.com/org/mcp-server

    Returns:
        allowed (bool): Whether the MCP is safe to run under current policy.
        reason (str): Human-readable explanation.
        security_score (int): 0-100 security score.
        risk_level (str): none | low | medium | high | critical.
        blocked_by_policy (list[str]): Policy violations causing a block.
        capabilities (list[str]): MCP capabilities detected in the repo.
        denied_capabilities_found (list[str]): Detected capabilities that violate policy.
        owasp_risks (list[str]): Triggered OWASP MCP Top 10 identifiers.
        findings_summary (dict): Counts keyed by severity.
        critical_findings (list[dict]): Full detail for every critical finding.
        high_findings (list[dict]): Full detail for every high-severity finding.
        credits_consumed (int): Credits spent for this operation.
        credits_remaining (int | None): Balance after the operation.
        scan_id (str): Scan identifier for follow-up queries.
    """
    cfg = get_mcp_config()

    submit_resp = api_request(
        "POST", "/scans/",
        {"url": url, "turnstile_token": ""},
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
    check_token = _extract_check_token(submit_resp)

    deadline = time.monotonic() + cfg.poll_timeout
    scan_id: str | None = None
    status_resp: dict[str, Any] = {}
    while time.monotonic() < deadline:
        status_resp = api_request(
            "GET", f"/scans/checking/{check_token}/",
            api_key=cfg.api_key, api_url=cfg.api_url,
        )
        status = status_resp.get("status")
        if status == "resolved":
            scan_id = str(status_resp.get("scan_id", ""))
            break
        if status == "error":
            raise RuntimeError(f"Scan failed: {status_resp.get('error', 'unknown error')}")
        time.sleep(cfg.poll_interval)
    else:
        raise RuntimeError(f"Scan timed out after {cfg.poll_timeout}s")

    if not scan_id:
        raise RuntimeError(f"No scan_id in resolved response: {status_resp}")

    verdict = api_request(
        "GET", f"/scans/{scan_id}/verdict/",
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
    return _build_mcp_response(verdict, scan_id, cfg)


def get_verdict(scan_id: str) -> dict[str, Any]:
    """Get the security verdict for a previously scanned repository and evaluate policy.

    Args:
        scan_id: Scan UUID returned by a previous check_mcp_safety() call.

    Returns:
        Same structure as check_mcp_safety().
    """
    cfg = get_mcp_config()
    verdict = api_request(
        "GET", f"/scans/{scan_id}/verdict/",
        api_key=cfg.api_key, api_url=cfg.api_url,
    )
    return _build_mcp_response(verdict, scan_id, cfg)


def get_scan_result(scan_id: str) -> dict[str, Any]:
    """Get the full security scan result for a previously submitted scan.

    Returns complete findings with file paths, line numbers, CWE IDs, and remediation
    guidance. Auto-unlocks the report (consuming 5 credits) if not already unlocked.

    Args:
        scan_id: Scan UUID returned by a previous check_mcp_safety() call.
    """
    cfg = get_mcp_config()
    return api_request(
        "GET", f"/scans/{scan_id}/result/",
        api_key=cfg.api_key, api_url=cfg.api_url,
    )


def get_credit_balance() -> dict[str, Any]:
    """Check your current MCP Hub credit balance.

    Returns:
        credits (float): Current credit balance.
        email (str): Account email address.
    """
    cfg = get_mcp_config()
    me = api_request("GET", "/user/me/", api_key=cfg.api_key, api_url=cfg.api_url)
    return {
        "credits": me.get("credit_balance", 0),
        "email": me.get("email", ""),
    }
