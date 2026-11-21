"""AST dependency graph and impact-closure unit tests."""
from pathlib import Path

from backend.app.analysis.ast_graph import build_dependents, impacted_closure, normalize_manifest_path, scan_imports
from backend.app.analysis.impact import analyze_change

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_scan_imports_finds_expected_edges() -> None:
    graph = scan_imports(PROJECT_ROOT)
    assert "sample_app.payments" in graph["sample_app.orders"]
    assert "sample_app.customers" in graph["sample_app.orders"]
    assert "sample_app.search" in graph["sample_app.orders"]
    assert "sample_app.orders" in graph["sample_app.reports"]
    assert "sample_app.auth" in graph["sample_app.admin"]
    assert graph["sample_app.auth"] == set()
    assert len(graph) == 7


def test_build_dependents_is_reverse_graph() -> None:
    graph = scan_imports(PROJECT_ROOT)
    dependents = build_dependents(graph)
    assert "sample_app.orders" in dependents["sample_app.payments"]
    assert "sample_app.reports" in dependents["sample_app.orders"]
    assert dependents["sample_app.reports"] == set()


def test_normalize_manifest_paths() -> None:
    assert normalize_manifest_path("sample_app/payments.py", PROJECT_ROOT) == "sample_app.payments"
    assert normalize_manifest_path("sample_app\\payments.py", PROJECT_ROOT) == "sample_app.payments"
    assert normalize_manifest_path("docs/readme.md", PROJECT_ROOT) is None
    assert normalize_manifest_path("sample_app/nonexistent.py", PROJECT_ROOT) is None


def test_payments_change_closure_includes_orders_and_reports() -> None:
    result = analyze_change([{"path": "sample_app/payments.py", "functions_changed": ["validate_amount"]}])
    assert result.changed_modules == ["sample_app.payments"]
    assert result.impacted_modules == ["sample_app.orders", "sample_app.payments", "sample_app.reports"]
    reasons = {entry["module"]: entry["reason"] for entry in result.payload["impacted_modules"]}
    assert "directly changed by manifest" in reasons["sample_app.payments"]
    assert "depends on sample_app.payments via import" in reasons["sample_app.orders"]


def test_auth_change_closure_admin_only() -> None:
    result = analyze_change([{"path": "sample_app/auth.py", "functions_changed": ["verify_token"]}])
    assert set(result.impacted_modules) == {"sample_app.auth", "sample_app.admin"}


def test_outside_package_paths_are_ignored() -> None:
    result = analyze_change(
        [
            {"path": "docs/readme.md", "functions_changed": []},
            {"path": "frontend/index.html", "functions_changed": []},
        ]
    )
    assert result.changed_modules == []
    assert result.impacted_modules == []
    assert result.payload["ignored_paths"] == ["docs/readme.md", "frontend/index.html"]


def test_impacted_closure_empty_input() -> None:
    graph = {"a": set(), "b": {"a"}}
    dependents = build_dependents(graph)
    impacted, stats = impacted_closure([], graph, dependents)
    assert impacted == []
    assert stats["graph_nodes"] == 2 and stats["graph_edges"] == 1


def test_transitive_closure_depth() -> None:
    graph = {"a": set(), "b": {"a"}, "c": {"b"}, "d": {"c"}}
    dependents = build_dependents(graph)
    impacted, _ = impacted_closure(["a"], graph, dependents)
    modules = [entry["module"] for entry in impacted]
    assert modules == ["a", "b", "c", "d"]
