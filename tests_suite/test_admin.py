import pytest

from sample_app import auth as auth_mod
from sample_app.admin import require_permission


@pytest.fixture()
def admin_token() -> str:
    return auth_mod.issue_token("qa_admin", "s3cret!")["token"]


def test_admin_require_permission_allows_role(admin_token: str) -> None:
    payload = require_permission(admin_token, "money.refund")
    assert payload["username"] == "qa_admin"


def test_admin_require_permission_denies_role() -> None:
    viewer = auth_mod.issue_token("viewer", "look")["token"]
    with pytest.raises(PermissionError, match="missing permission"):
        require_permission(viewer, "users.manage")
    with pytest.raises(PermissionError, match="authentication failed"):
        require_permission("not-a-token", "reports.view")
