"""Injected regression produces a real failure caught by selection and RCA."""
from backend.tests.conftest import PAYMENTS_MANIFEST


def test_injected_bug_fails_boundary_test_and_blocks_gate(api_client) -> None:
    api_client.post("/api/v1/bugs/payments/on")
    try:
        change = api_client.post("/api/v1/changes", json=PAYMENTS_MANIFEST).json()
        summary = api_client.post(f"/api/v1/changes/{change['id']}/analyze").json()
        assert summary["executed_failed"] >= 8
        assert summary["decision"] == "block"
        assert summary["confidence"] < 60.0
        execution = api_client.get(f"/api/v1/changes/{change['id']}/execution").json()
        failed_nodes = [r["node_id"] for r in execution["results"] if r["outcome"] == "failed"]
        assert "tests_suite/test_payments.py::test_validate_amount_rejects_above_limit" in failed_nodes
        failures = api_client.get(f"/api/v1/changes/{change['id']}/failures").json()
        boundary = next(f for f in failures["failures"] if f["test_id"] == "payments_boundary_above_limit")
        assert "DID NOT RAISE" in boundary["stack_trace"] or "PaymentError" in boundary["stack_trace"]
        rca = boundary["rca"]
        assert "Injected regression" in rca["root_cause"]
        assert rca["confidence"] >= 0.9
        assert any(".qe_bug_payments" in e or "QE_BUG_PAYMENTS" in e for e in rca["evidence"])
    finally:
        off = api_client.post("/api/v1/bugs/payments/off").json()
        assert off["active"] is False


def test_clean_run_has_no_failures_for_same_change(api_client) -> None:
    change = api_client.post("/api/v1/changes", json=PAYMENTS_MANIFEST).json()
    summary = api_client.post(f"/api/v1/changes/{change['id']}/analyze").json()
    assert summary["executed_failed"] == 0
    assert summary["confidence"] == 100.0
    assert summary["decision"] == "allow"
