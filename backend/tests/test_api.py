"""API surface: health, readiness, metrics, dashboard, changes, bugs, registry."""
from backend.tests.conftest import AUTH_MANIFEST


def test_health_and_readiness(api_client) -> None:
    assert api_client.get("/health").json() == {"status": "ok", "service": "qe-release-confidence-agent"}
    readiness = api_client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["ready"] is True and readiness.json()["seeded"] is True


def test_metrics_endpoint_prometheus_text(api_client) -> None:
    text = api_client.get("/metrics").text
    assert "# HELP qe_changes_submitted_total" in text
    assert "# TYPE qe_last_confidence_score gauge" in text


def test_dashboard_served(api_client) -> None:
    response = api_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Release Confidence" in response.text


def test_submit_change_creates_workflow(api_client) -> None:
    created = api_client.post("/api/v1/changes", json=AUTH_MANIFEST)
    assert created.status_code == 201
    body = created.json()
    assert body["workflow_state"] == "PROPOSED"
    listing = api_client.get("/api/v1/changes").json()
    assert any(row["id"] == body["id"] for row in listing)
    assert listing[0]["workflow_state"] == "PROPOSED"


def test_artifacts_404_before_analysis(api_client) -> None:
    change = api_client.post("/api/v1/changes", json=AUTH_MANIFEST).json()
    for suffix in ("impact", "selection", "execution", "confidence", "gate"):
        assert api_client.get(f"/api/v1/changes/{change['id']}/{suffix}").status_code == 404
    empty_failures = api_client.get(f"/api/v1/changes/{change['id']}/failures").json()
    assert empty_failures["failures"] == []
    assert api_client.get("/api/v1/changes/9999/impact").status_code == 404


def test_registry_lists_seeded_tests(api_client) -> None:
    registry = api_client.get("/api/v1/tests/registry").json()
    assert len(registry) == 30
    types = {row["test_type"] for row in registry}
    assert {"unit", "api", "integration", "contract", "smoke"} <= types
    flaky = [row for row in registry if row["flakiness_score"] >= 0.3]
    assert len(flaky) == 2
    boundary = next(row for row in registry if row["test_id"] == "payments_boundary_above_limit")
    assert boundary["security_relevant"] is True


def test_bug_toggle_endpoints(api_client) -> None:
    on = api_client.post("/api/v1/bugs/payments/on")
    assert on.status_code == 200 and on.json()["active"] is True
    off = api_client.post("/api/v1/bugs/payments/off")
    assert off.json()["active"] is False
    bad = api_client.post("/api/v1/bugs/payments/sideways")
    assert bad.status_code == 422


def test_analyze_requires_existing_change(api_client) -> None:
    assert api_client.post("/api/v1/changes/424242/analyze").status_code == 404


def test_manifest_validation_rejects_empty_files(api_client) -> None:
    response = api_client.post("/api/v1/changes", json={"title": "bad", "files": []})
    assert response.status_code == 422
