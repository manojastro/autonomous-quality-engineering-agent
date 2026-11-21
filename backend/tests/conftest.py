"""Shared fixtures: isolated per-test database and API client."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("QE_FLAKY_ACTIVE", "")


@pytest.fixture()
def api_client(tmp_path: Path):
    os.environ["QE_DB_URL"] = f"sqlite:///{(tmp_path / 'qe_test.db').as_posix()}"
    from backend.app.db import dispose_engine
    from backend.app.main import app
    from backend.app.services import metrics as metrics_mod

    dispose_engine()
    with TestClient(app) as client:
        yield client
    dispose_engine()
    metrics_mod._counters.clear()
    metrics_mod._labeled.clear()
    metrics_mod._gauges.clear()


@pytest.fixture(autouse=True)
def _clean_sample_app_state():
    from sample_app.payments import set_bug_state

    set_bug_state(False)
    yield
    set_bug_state(False)
    state_dir = PROJECT_ROOT / "tests_suite" / ".flaky_state"
    if state_dir.exists():
        shutil.rmtree(state_dir, ignore_errors=True)


@pytest.fixture()
def session_with_seed(tmp_path: Path):
    os.environ["QE_DB_URL"] = f"sqlite:///{(tmp_path / 'qe_tools.db').as_posix()}"
    from backend.app.db import dispose_engine, get_session, init_engine
    from backend.app.services.seeder import seed

    dispose_engine()
    init_engine(f"sqlite:///{(tmp_path / 'qe_tools.db').as_posix()}")
    from backend.app.db import create_all

    create_all()
    session = get_session()
    seed(session)
    yield session
    session.rollback()
    session.close()
    dispose_engine()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


PAYMENTS_MANIFEST = {
    "title": "Tighten payment validation",
    "files": [
        {
            "path": "sample_app/payments.py",
            "functions_changed": ["validate_amount", "transaction_fee"],
            "lines_added": 18,
            "lines_deleted": 4,
        }
    ],
}

AUTH_MANIFEST = {
    "title": "Token TTL handling",
    "files": [
        {"path": "sample_app/auth.py", "functions_changed": ["verify_token"], "lines_added": 8, "lines_deleted": 2}
    ],
}
