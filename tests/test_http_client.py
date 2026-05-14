from __future__ import annotations
import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from mcp_hub_security.http_client import api_request


def _make_response(data: dict):
    body = json.dumps(data).encode()
    mock = MagicMock()
    mock.read.return_value = body
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_get_request_returns_parsed_json():
    payload = {"key": "value", "num": 42}
    with patch("urllib.request.urlopen", return_value=_make_response(payload)):
        result = api_request("GET", "/test", api_key="k", api_url="https://api.example.com/v1")
    assert result == payload


def test_request_sets_bearer_auth():
    captured = []

    def fake_urlopen(req, timeout):
        captured.append(req)
        return _make_response({})

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        api_request("GET", "/path", api_key="secret-key", api_url="https://api.example.com/v1")

    assert captured[0].get_header("Authorization") == "Bearer secret-key"


def test_missing_api_key_raises_before_http_call():
    with pytest.raises(RuntimeError, match="MCPHUB_API_KEY"):
        api_request("GET", "/path", api_key="", api_url="https://api.example.com/v1")


def test_http_error_raises_runtime_error():
    err_body = json.dumps({"detail": "Not found"}).encode()
    http_err = urllib.error.HTTPError(
        url="https://api.example.com/v1/path",
        code=404,
        msg="Not Found",
        hdrs={},  # type: ignore[arg-type]
        fp=BytesIO(err_body),
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(RuntimeError, match="API error 404"):
            api_request("GET", "/path", api_key="k", api_url="https://api.example.com/v1")


def test_post_request_sends_json_body():
    captured = []

    def fake_urlopen(req, timeout):
        captured.append(req)
        return _make_response({"ok": True})

    body = {"url": "https://github.com/org/repo"}
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        api_request("POST", "/scans/", body, api_key="k", api_url="https://api.example.com/v1")

    sent = json.loads(captured[0].data)
    assert sent == body
