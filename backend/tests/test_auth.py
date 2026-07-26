from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import get_current_user_id

#Tests created by Claude AI

def _fake_request(auth_header: str | None) -> Request:
    headers = [(b"authorization", auth_header.encode())] if auth_header else []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/papers",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


def test_valid_token_returns_user_id():
    fake_state = MagicMock(is_signed_in=True, payload={"sub": "user_abc123"})
    with patch("app.core.auth._clerk_client.authenticate_request", return_value=fake_state):
        user_id = get_current_user_id(_fake_request("Bearer valid.token.here"))
    assert user_id == "user_abc123"


def test_missing_token_raises_401():
    fake_state = MagicMock(is_signed_in=False, payload=None)
    with patch("app.core.auth._clerk_client.authenticate_request", return_value=fake_state):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_fake_request(None))
    assert exc_info.value.status_code == 401


def test_expired_or_invalid_token_raises_401():
    fake_state = MagicMock(is_signed_in=False, payload=None)
    with patch("app.core.auth._clerk_client.authenticate_request", return_value=fake_state):
        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(_fake_request("Bearer expired.token.here"))
    assert exc_info.value.status_code == 401
