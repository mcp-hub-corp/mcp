from __future__ import annotations
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from mcp_hub_security import __version__ as _PKG_VERSION
from mcp_hub_security.validators import (
    SchemaValidationError,
    validate_scan_response,
)


# M4-025: identify the hub HTTP client to the API so the server side can
# spot outdated watchdog versions, rate-limit per agent and produce
# meaningful audit logs. Format follows RFC 9110 §10.1.5 (token/version
# with optional comment).
USER_AGENT = f"mcp-hub-security/{_PKG_VERSION} (+https://mcp-hub.info)"


# M4-019: Optional public-key/cert pinning. Set
# ``MCPHUB_CERT_FINGERPRINT_SHA256`` to the hex SHA-256 of the *DER-encoded*
# server certificate (use ``openssl x509 -in cert.pem -outform DER | sha256sum``
# or ``echo | openssl s_client -connect api.mcp-hub.info:443 -servername
# api.mcp-hub.info 2>/dev/null | openssl x509 -outform DER | sha256sum``). When
# set, every HTTPS request validates the leaf certificate fingerprint and
# raises if it doesn't match. Empty / unset means standard CA validation only.
_PIN_ENV_VAR = "MCPHUB_CERT_FINGERPRINT_SHA256"


class CertPinningError(RuntimeError):
    """Raised when MCPHUB_CERT_FINGERPRINT_SHA256 doesn't match the server."""


def _expected_fingerprint() -> str | None:
    raw = os.environ.get(_PIN_ENV_VAR)
    if not raw:
        return None
    # Accept ``aa:bb:cc:...`` or plain hex; lowercase for comparison.
    return raw.replace(":", "").strip().lower() or None


def _verify_pin(url: str) -> None:
    """If pinning is enabled, fetch the leaf cert and compare the SHA-256.

    This is a defensive *additional* check on top of standard TLS validation.
    The cost is one extra TLS handshake per request; only enable when needed.
    """
    expected = _expected_fingerprint()
    if expected is None:
        return
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise CertPinningError(
            f"cert pinning enabled but URL is not HTTPS: {url!r}"
        )
    import socket  # local import — only loaded when pinning active

    host = parsed.hostname or ""
    port = parsed.port or 443
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=10) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            der = ssock.getpeercert(binary_form=True)
    if der is None:
        raise CertPinningError(f"could not read peer certificate for {host}")
    actual = hashlib.sha256(der).hexdigest()
    if actual != expected:
        raise CertPinningError(
            f"cert fingerprint mismatch for {host}: expected {expected}, got {actual}"
        )


def api_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    api_key: str,
    api_url: str,
    timeout: float = 30.0,
    validate_schema: bool = False,
) -> dict[str, Any]:
    """Authenticated request to the MCP Hub API. Raises RuntimeError on HTTP errors.

    ``validate_schema=True`` runs the response through
    ``validate_scan_response`` and raises ``SchemaValidationError`` on
    contract violations. Use for endpoints returning a scan/skill result.
    """
    if not api_key:
        raise RuntimeError("MCPHUB_API_KEY environment variable is not set.")

    url = f"{api_url}{path}"

    # M4-019: enforce cert pinning if configured (TLS validation by default is
    # already on through urllib's default SSLContext).
    _verify_pin(url)

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # M4-025: stamp the client identity on every request so the
            # hub can correlate requests, rate-limit per agent and warn
            # users running outdated watchdog versions.
            "User-Agent": USER_AGENT,
        },
    )
    # Explicit default SSL context — never disable verification.
    ssl_context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        raise RuntimeError(f"API error {exc.code}: {detail}") from exc

    if validate_schema:
        try:
            validate_scan_response(payload)
        except SchemaValidationError as exc:
            raise RuntimeError(f"hub contract violation: {exc}") from exc
    return payload
