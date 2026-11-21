"""Selection math: minimum high-value set, skip reasons, precision/recall."""
from backend.app.analysis.ground_truth import LABELED_CASES
from backend.app.analysis.impact import analyze_change
from backend.app.analysis.selection import selection_precision_recall, select_tests
from backend.app.services.seeder import TEST_REGISTRY


class _Reg:
    def __init__(self, fields: dict) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


REGISTRY = [_Reg(fields) for fields in TEST_REGISTRY]
BY_ID = {row.test_id: row for row in REGISTRY}


def _selected_ids(impacted_modules: list[str]) -> set[str]:
    plan = select_tests(REGISTRY, impacted_modules)
    return {item["test_id"] for item in plan["selected"]}


def test_payments_impact_selects_expected_subset() -> None:
    impact = analyze_change([{"path": "sample_app/payments.py", "functions_changed": ["validate_amount"]}])
    plan = select_tests(REGISTRY, impact.impacted_modules)
    selected = {item["test_id"] for item in plan["selected"]}
    assert "payments_boundary_above_limit" in selected
    assert "checkout_e2e_flow" in selected
    assert "contract_payments_orders" in selected
    assert "smoke_critical_path" in selected
    assert "reports_daily_revenue" in selected
    assert "auth_bearer_token" not in selected
    assert "flaky_search_refresh" not in selected
    assert plan["total_tests"] == 30
    assert plan["selected_count"] == 18
    assert plan["reduction_pct"] == 40.0


def test_unrelated_change_selects_only_smoke() -> None:
    plan = select_tests(REGISTRY, [])
    assert [item["test_id"] for item in plan["selected"]] == ["smoke_critical_path"]
    assert plan["reduction_pct"] >= 95.0
    assert all("unaffected" in item["reason"] for item in plan["skipped"])
    assert len(plan["skipped"]) == 29


def test_auth_impact_includes_flaky_watch_and_admin() -> None:
    selected = _selected_ids(["sample_app.auth", "sample_app.admin"])
    assert "admin_permission_allow" in selected
    assert "admin_permission_deny" in selected
    assert "flaky_auth_handshake" in selected
    assert "smoke_critical_path" in selected
    rationale = next(item["rationale"] for item in select_tests(REGISTRY, ["sample_app.auth", "sample_app.admin"])["selected"] if item["test_id"] == "flaky_auth_handshake")
    assert "flakiness watch" in rationale


def test_skip_reasons_name_mapped_modules() -> None:
    plan = select_tests(REGISTRY, ["sample_app.payments", "sample_app.orders", "sample_app.reports"])
    skipped = {item["test_id"]: item["reason"] for item in plan["skipped"]}
    assert "auth_token_expiry" in skipped
    assert "sample_app.auth" in skipped["auth_token_expiry"]


def test_precision_recall_perfect_on_labeled_cases() -> None:
    misses: list[str] = []
    for case in LABELED_CASES:
        if case["name"] == "unrelated_docs_change":
            continue
        impact = analyze_change(case["manifest"]["files"])
        plan = select_tests(REGISTRY, impact.impacted_modules)
        pr = selection_precision_recall(plan["selected"], BY_ID, case["true_impacted_modules"])
        if pr["precision"] != 1.0 or pr["recall"] != 1.0:
            misses.append(case["name"])
    assert misses == []


def test_negative_case_flags_mandatory_smoke_overhead() -> None:
    pr = selection_precision_recall(
        [{"test_id": "smoke_critical_path", "test_type": "smoke"}],
        BY_ID,
        [],
    )
    assert pr["false_positives"] == 0 and pr["precision"] == 1.0
