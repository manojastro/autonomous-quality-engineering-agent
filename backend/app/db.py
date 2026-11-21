"""SQLAlchemy engine/session management."""
from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_engine(db_url: str) -> Engine:
    global _engine, _session_factory
    _engine = create_engine(db_url, future=True, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        init_engine("sqlite://")
    assert _engine is not None
    return _engine


def get_session() -> Session:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    return _session_factory()


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def ping() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def create_all() -> None:
    from backend.app.models import Base

    Base.metadata.create_all(get_engine())


def reset_all() -> None:
    from backend.app.models import Base

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def modules_seeded(session: Session) -> bool:
    from sqlalchemy import select

    from backend.app.models import Module

    return session.execute(select(Module)).scalars().first() is not None
