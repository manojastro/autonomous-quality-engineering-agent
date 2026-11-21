"""Shared request-scoped dependencies."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from backend.app.db import get_session
from backend.app.tools import default_registry


def db_session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def tools() -> default_registry.__class__:
    return default_registry
