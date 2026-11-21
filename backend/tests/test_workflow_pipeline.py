"""Full pipeline workflow through the API with a small change."""
from backend.tests.conftest import AUTH_MANIFEST


def test_analyze_auth_change_end_to_end(api_client) -> None:
    change = api_client.post("/api/v1/changes", json=AUTH_MANIFEST).json()
    summary = api_client.post(f"/api/v1/changes/{change['id']}/analyze").json()
    assert summary["impacted_modules"] == ["sample_app.admin", "sample_app.auth"]
    assert summary["selected_count"] == 7
    assert summary["total_tests"] == 30
    assert summary["reduction_pct"] == round(100.0 * 23 / 30, 1)
    assert summary["executed_total"] == 7
    assert summary["executed_failed"] == 0
    assert summary["confidence"] >= 85.0
    assert summary["decision"] == "allow"
    assert summary["workflow_state"] == "AWAITING_APPROVAL"

    selection = api_client.get(f"/api/v1/changes/{change['id']}/selection").json()
    selected_ids = {item["test_id"] for item in selection["selected"]}
    assert {"auth_bearer_token", "auth_token_expiry", "auth_bad_password", "admin_permission_allow", "admin_permission_deny", "flaky_auth_handshake", "smoke_critical_path"} == selected_ids
    assert selection["narrative"]
    assert all("priority_score" in item for item in selection["selected"])
    assert selection["selected"][0]["priority_score"] >= selection["selected"][-1]["priority_score"]


def test_flaky_report_written_for_watch_listed_test(api_client) -> None:
    change = api_client.post("/api/v1/changes", json=AUTH_MANIFEST).json()
    api_client.post(f"/api/v1/changes/{change['id']}/analyze")
    flaky = api_client.get(f"/api/v1/changes/{change['id']}/flaky").json()
    classified = {entry["test_id"]: entry["classification"] for entry in flaky["entries"]}
    assert classified.get("flaky_auth_handshake") in ("unknown", "flaky_test")


def test_reanalyze_blocked_after_terminal_state(api_client) -> None:
    change = api_client.post("/api/v1/changes", json=AUTH_MANIFEST).json()
    api_client.post(f"/api/v1/changes/{change['id']}/analyze")
    gate = api_client.get(f"/api/v1/changes/{change['id']}/gate").json()
    override = api_client.post(
        f"/api/v1/gates/{gate['gate_id']}/override",
        json={"action": "approve", "approver": "qa-lead", "justification": "green"},
    )
    assert override.status_code == 200
    rerun = api_client.post(f"/api/v1/changes/{change['id']}/analyze")
    assert rerun.status_code == 409
    assert "terminal" in rerun.json()["detail"]
