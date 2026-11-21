"""Admin permission enforcement built on auth tokens."""
from __future__ import annotations

from sample_app.auth import AuthError, verify_token

ROLE_PERMISSIONS = {
    "admin": {"users.manage", "money.refund", "config.write", "reports.view"},
    "analyst": {"reports.view"},
    "viewer": set(),
}


def require_permission(token: str, permission: str) -> dict:
    """Verify a bearer token grants the requested permission."""
    try:
        payload = verify_token(token)
    except AuthError as exc:
        raise PermissionError(f"authentication failed: {exc}") from exc
    granted = ROLE_PERMISSIONS.get(payload["role"], set())
    if permission not in granted:
        raise PermissionError(f"role {payload['role']} missing permission {permission}")
    return payload
