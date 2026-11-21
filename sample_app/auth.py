"""Authentication with token issuance and expiry enforcement."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Dict, Optional

CREDENTIALS: Dict[str, dict] = {
    "qa_admin": {"password": "s3cret!", "role": "admin"},
    "analyst": {"password": "peek", "role": "analyst"},
    "viewer": {"password": "look", "role": "viewer"},
}

TOKEN_TTL_SECONDS = 300

_ACTIVE_TOKENS: Dict[str, dict] = {}


class AuthError(PermissionError):
    """Raised on authentication or authorization failures."""


def _hash(username: str, password: str) -> str:
    return hashlib.sha256(f"{username}:{password}".encode("utf-8")).hexdigest()


def login(username: str, password: str) -> dict:
    record = CREDENTIALS.get(username)
    if record is None:
        raise AuthError("unknown user")
    if not hmac.compare_digest(_hash(username, password), _hash(username, record["password"])):
        raise AuthError("invalid credentials")
    return {"username": username, "role": record["role"]}


def issue_token(username: str, password: str, ttl_seconds: int = TOKEN_TTL_SECONDS) -> dict:
    principal = login(username, password)
    token = secrets.token_hex(16)
    issued = time.time()
    _ACTIVE_TOKENS[token] = {**principal, "issued_at": issued, "expires_at": issued + ttl_seconds}
    return {"token": token, "token_type": "Bearer", "expires_at": _ACTIVE_TOKENS[token]["expires_at"], "role": principal["role"]}


def verify_token(token: str, now: Optional[float] = None) -> dict:
    payload = _ACTIVE_TOKENS.get(token)
    if payload is None:
        raise AuthError("invalid or revoked token")
    current = time.time() if now is None else now
    if current >= payload["expires_at"]:
        _ACTIVE_TOKENS.pop(token, None)
        raise AuthError("token expired")
    return dict(payload)


def revoke_token(token: str) -> None:
    _ACTIVE_TOKENS.pop(token, None)


def reset_auth() -> None:
    _ACTIVE_TOKENS.clear()
