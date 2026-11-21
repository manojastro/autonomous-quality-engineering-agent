import time

import pytest

from sample_app import auth
from sample_app.auth import AuthError, issue_token, login, verify_token


def test_issue_token_returns_bearer() -> None:
    issued = issue_token("qa_admin", "s3cret!", ttl_seconds=60)
    assert issued["token_type"] == "Bearer"
    payload = verify_token(issued["token"])
    assert payload["role"] == "admin"


def test_token_expiry_enforced() -> None:
    issued = issue_token("viewer", "look", ttl_seconds=-1)
    time.sleep(0.01)
    with pytest.raises(AuthError, match="expired"):
        verify_token(issued["token"])


def test_login_rejects_bad_password() -> None:
    with pytest.raises(AuthError):
        login("analyst", "wrong")
    with pytest.raises(AuthError):
        login("ghost", "peek")
