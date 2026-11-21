"""Workflow state machine: legal pipeline path and 409 on illegal transitions."""
import pytest

from backend.app.services.workflow import TERMINAL_STATES, TRANSITIONS, ApprovalService, WorkflowError


def test_transition_table_covers_all_states() -> None:
    assert set(TRANSITIONS) == {
        "PROPOSED", "VALIDATING", "EXECUTING", "VERIFYING",
        "AWAITING_APPROVAL", "APPROVED", "COMPLETED", "FAILED", "ROLLED_BACK",
    }
    for state in TERMINAL_STATES:
        assert TRANSITIONS[state] == set()


def test_full_pipeline_transitions_are_legal(api_client) -> None:
    change = api_client.post("/api/v1/changes", json={
        "title": "docs only",
        "files": [{"path": "docs/readme.md", "functions_changed": [], "lines_added": 3, "lines_deleted": 1}],
    }).json()
    summary = api_client.post(f"/api/v1/changes/{change['id']}/analyze").json()
    assert summary["workflow_state"] == "AWAITING_APPROVAL"
    gate = api_client.get(f"/api/v1/changes/{change['id']}/gate").json()
    override = api_client.post(f"/api/v1/gates/{gate['gate_id']}/override", json={"action": "approve", "approver": "qa-lead", "justification": "smoke green"})
    assert override.status_code == 200
    assert override.json()["workflow_state"] == "APPROVED"
    second = api_client.post(f"/api/v1/gates/{gate['gate_id']}/override", json={"action": "reject", "approver": "qa-lead", "justification": "already decided"})
    assert second.status_code == 409


def test_override_unknown_gate_returns_404(api_client) -> None:
    response = api_client.post("/api/v1/gates/999999/override", json={"action": "approve", "approver": "qa-lead", "justification": "n/a"})
    assert response.status_code == 404


def test_blocked_override_needs_substantive_justification(api_client) -> None:
    from backend.tests.conftest import PAYMENTS_MANIFEST

    api_client.post("/api/v1/bugs/payments/on")
    try:
        change = api_client.post("/api/v1/changes", json=PAYMENTS_MANIFEST).json()
        api_client.post(f"/api/v1/changes/{change['id']}/analyze")
        gate = api_client.get(f"/api/v1/changes/{change['id']}/gate").json()
        weak = api_client.post(f"/api/v1/gates/{gate['gate_id']}/override", json={"action": "approve", "approver": "release-manager", "justification": "ok"})
        assert weak.status_code == 409
        strong = api_client.post(f"/api/v1/gates/{gate['gate_id']}/override", json={"action": "approve", "approver": "release-manager", "justification": "hotfix approved by incident commander INC-1234, payments boundary risk accepted"})
        assert strong.status_code == 200
        assert strong.json()["effective_release"] == "allowed_with_override"
    finally:
        api_client.post("/api/v1/bugs/payments/off")


def test_illegal_direct_transition_rejected(api_client) -> None:
    from backend.app.db import get_session

    change = api_client.post("/api/v1/changes", json={
        "title": "reports tweak",
        "files": [{"path": "sample_app/reports.py", "functions_changed": ["daily_revenue"], "lines_added": 2, "lines_deleted": 1}],
    }).json()
    session = get_session()
    try:
        service = ApprovalService(session)
        with pytest.raises(WorkflowError):
            service.transition(change["id"], "COMPLETED")
    finally:
        session.rollback()
        session.close()
