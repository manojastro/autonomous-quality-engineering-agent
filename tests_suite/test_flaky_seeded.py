"""Seeded-flaky tests.

Alternating behaviour is gated behind QE_FLAKY_ACTIVE=1 so routine suite runs
stay deterministic while the agent's execution and retry policies exercise the
real alternation mechanics.
"""
import os
from pathlib import Path

import pytest

_STATE_DIR = Path(__file__).parent / ".flaky_state"


def _should_fail(name: str) -> bool:
    if os.environ.get("QE_FLAKY_ACTIVE") != "1":
        return False
    counter = _STATE_DIR / f"{name}.count"
    try:
        n = int(counter.read_text(encoding="utf-8").strip() or "0") + 1
    except (OSError, ValueError):
        n = 1
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    counter.write_text(str(n), encoding="utf-8")
    return n % 2 == 0


def test_flaky_search_index_refresh() -> None:
    if _should_fail("alpha"):
        pytest.fail("search index refresh timed out waiting for cluster green (intermittent)")


def test_flaky_auth_provider_handshake() -> None:
    if _should_fail("beta"):
        pytest.fail("auth provider handshake dropped connection during token exchange (intermittent)")
