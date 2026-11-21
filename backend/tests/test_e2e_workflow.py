"""End-to-end workflow: block on defect, override rules, allow after fix."""
from backend.tests.conftest import PAYMENTS_MANIFEST


def test_full_block_then_allow_cycle(api_client) -> None:
    api_client.post("/api/v1/bugs/payments/on")
    bad_change = api_client.post("/api/v1/changes", json=PAYMENTS_MANIFEST).json()
    bad_summary = api_client.post(f"/api/v1/changes/{bad_change['id']}/analyze").json()

    assert bad_summary["impacted_modules"] == ["sample_app.orders", "sample_app.payments", "sample_app.reports"]
    assert bad_summary["selected_count"] < bad_summary["total_tests"]
    reduction_expected = round(100.0 * (bad_summary["total_tests"] - bad_summary["selected_count"]) / bad_summary["total_tests"], 1)
    assert bad_summary["reduction_pct"] == reduction_expected
    assert bad_summary["executed_failed"] > 0
    assert bad_summary["failures"] == bad_summary["executed_failed"]
    assert bad_summary["decision"] == "block"
    assert bad_summary["workflow_state"] == "AWAITING_APPROVAL"

    bad_gate = api_client.get(f"/api/v1/changes/{bad_change['id']}/gate").json()
    weak_override = api_client.post(
        f"/api/v1/gates/{bad_gate['gate_id']}/override",
        json={"action": "approve", "approver": "release-manager", "justification": "nope"},
    )
    assert weak_override.status_code == 409
    strong_override = api_client.post(
        f"/api/v1/gates/{bad_gate['gate_id']}/override",
        json={"action": "approve", "approver": "release-manager", "justification": "incident INC-42 accepted risk; fix scheduled tonight"},
    )
    assert strong_override.status_code == 200

    api_client.post("/api/v1/bugs/payments/off")
    good_change = api_client.post("/api/v1/changes", json=PAYMENTS_MANIFEST).json()
    good_summary = api_client.post(f"/api/v1/changes/{good_change['id']}/analyze").json()
    assert good_summary["executed_failed"] == 0
    assert good_summary["confidence"] > bad_summary["confidence"]
    assert good_summary["decision"] == "allow"

    kpis = api_client.get("/api/v1/kpis").json()
    assert kpis["selection_recall_avg"] >= 0.99
    assert kpis["missed_regressions"] == 0
    agreement = kpis["confidence_agreement"]
    assert agreement["evaluated"] >= 2
    assert agreement["accuracy"] == 1.0


def test_metrics_reflect_pipeline_activity(api_client) -> None:
    change = api_client.post("/api/v1/changes", json={
        "title": "admin perms",
        "files": [{"path": "sample_app/admin.py", "functions_changed": ["require_permission"], "lines_added": 5, "lines_deleted": 2}],
    }).json()
    summary = api_client.post(f"/api/v1/changes/{change['id']}/analyze").json()
    metrics_text = api_client.get("/metrics").text
    assert f'qe_gate_decisions_total{{action="{summary["decision"]}",decision="{summary["decision"]}"}} 1' in metrics_text
    assert "qe_tests_executed_total" in metrics_text
    lines = [line for line in metrics_text.splitlines() if line.startswith("qe_last_confidence_score")]
    assert lines and float(lines[0].split()[-1]) == summary["confidence"]
