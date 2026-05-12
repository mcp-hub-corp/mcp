from __future__ import annotations
import json
import urllib.error
import urllib.request
from typing import Any


def api_request(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    api_key: str,
    api_url: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Authenticated request to the MCP Hub API. Raises RuntimeError on HTTP errors."""
    if not api_key:
        raise RuntimeError("MCPHUB_API_KEY environment variable is not set.")

    url = f"{api_url}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        try:
            detail = json.loads(body_text).get("detail", body_text)
        except Exception:
            detail = body_text
        raise RuntimeError(f"API error {exc.code}: {detail}") from exc
