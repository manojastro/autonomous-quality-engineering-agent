"""Deterministic registry and module seeding."""
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models import CodeDependency, Module, TestRegistration

MODULES = [
    {"name": "sample_app.auth", "complexity": 4, "criticality": 5, "security_sensitive": True, "historical_defects": 2},
    {"name": "sample_app.customers", "complexity": 3, "criticality": 3, "security_sensitive": False, "historical_defects": 1},
    {"name": "sample_app.orders", "complexity": 7, "criticality": 5, "security_sensitive": False, "historical_defects": 4},
    {"name": "sample_app.payments", "complexity": 6, "criticality": 5, "security_sensitive": True, "historical_defects": 3},
    {"name": "sample_app.search", "complexity": 3, "criticality": 2, "security_sensitive": False, "historical_defects": 1},
    {"name": "sample_app.admin", "complexity": 2, "criticality": 4, "security_sensitive": True, "historical_defects": 1},
    {"name": "sample_app.reports", "complexity": 4, "criticality": 3, "security_sensitive": False, "historical_defects": 0},
]

DEPENDENCIES = [
    ("sample_app.orders", "sample_app.payments"),
    ("sample_app.orders", "sample_app.customers"),
    ("sample_app.orders", "sample_app.search"),
    ("sample_app.reports", "sample_app.orders"),
    ("sample_app.admin", "sample_app.auth"),
]


def _t(test_id: str, node: str, ttype: str, mappings: list[str], runtime: float, flakiness: float, history: list[str], security: bool = False) -> dict:
    return {
        "test_id": test_id,
        "node_id": node,
        "test_type": ttype,
        "module_mappings_json": mappings,
        "avg_runtime_s": runtime,
        "flakiness_score": flakiness,
        "historical_outcomes_json": history,
        "security_relevant": security,
    }


TEST_REGISTRY = [
    _t("payments_valid_amount", "tests_suite/test_payments.py::test_validate_amount_accepts_in_range", "unit", ["sample_app.payments"], 0.05, 0.0, ["pass"] * 10),
    _t("payments_non_positive", "tests_suite/test_payments.py::test_validate_amount_rejects_non_positive", "unit", ["sample_app.payments"], 0.04, 0.0, ["pass"] * 10),
    _t("payments_boundary_above_limit", "tests_suite/test_payments.py::test_validate_amount_rejects_above_limit", "unit", ["sample_app.payments"], 0.05, 0.1, ["pass", "pass", "fail", "pass", "pass", "pass"], security=True),
    _t("payments_fee_rounding", "tests_suite/test_payments.py::test_transaction_fee_uses_half_even_rounding", "unit", ["sample_app.payments"], 0.06, 0.0, ["pass", "pass", "fail", "fail", "pass"]),
    _t("payments_refund_net", "tests_suite/test_payments.py::test_refund_net_amount_math", "unit", ["sample_app.payments"], 0.05, 0.0, ["pass"] * 8),
    _t("payments_recurring_cycle", "tests_suite/test_payments.py::test_recurring_cycle_totals", "unit", ["sample_app.payments"], 0.07, 0.0, ["pass", "fail", "pass"]),
    _t("orders_receipt_totals", "tests_suite/test_orders.py::test_checkout_receipt_totals", "unit", ["sample_app.orders"], 0.09, 0.0, ["pass"] * 9),
    _t("orders_gold_discount", "tests_suite/test_orders.py::test_checkout_applies_gold_discount", "unit", ["sample_app.orders"], 0.08, 0.0, ["pass", "pass", "fail"]),
    _t("orders_inventory_guard", "tests_suite/test_orders.py::test_checkout_rejects_insufficient_inventory", "unit", ["sample_app.orders"], 0.05, 0.0, ["pass"] * 12),
    _t("orders_unknown_customer", "tests_suite/test_orders.py::test_checkout_requires_known_customer", "unit", ["sample_app.orders", "sample_app.customers"], 0.04, 0.0, ["pass"] * 11),
    _t("orders_refund_ledger", "tests_suite/test_orders.py::test_refund_flow_adjusts_ledger", "integration", ["sample_app.orders", "sample_app.payments"], 0.35, 0.0, ["pass"] * 7, security=True),
    _t("auth_bearer_token", "tests_suite/test_auth.py::test_issue_token_returns_bearer", "unit", ["sample_app.auth"], 0.05, 0.0, ["pass"] * 14),
    _t("auth_token_expiry", "tests_suite/test_auth.py::test_token_expiry_enforced", "unit", ["sample_app.auth"], 0.05, 0.0, ["pass", "fail", "pass"]),
    _t("auth_bad_password", "tests_suite/test_auth.py::test_login_rejects_bad_password", "unit", ["sample_app.auth"], 0.04, 0.0, ["pass"] * 13),
    _t("customers_roundtrip", "tests_suite/test_customers.py::test_register_customer_roundtrip", "unit", ["sample_app.customers"], 0.05, 0.0, ["pass"] * 9),
    _t("customers_credit_tiers", "tests_suite/test_customers.py::test_credit_limit_by_tier", "unit", ["sample_app.customers"], 0.05, 0.0, ["pass", "pass", "fail", "pass"]),
    _t("search_category_filter", "tests_suite/test_search.py::test_filter_by_category", "unit", ["sample_app.search"], 0.04, 0.0, ["pass"] * 10),
    _t("search_price_filter", "tests_suite/test_search.py::test_price_range_filter", "unit", ["sample_app.search"], 0.04, 0.0, ["pass"] * 10),
    _t("search_pagination", "tests_suite/test_search.py::test_pagination_window", "unit", ["sample_app.search"], 0.04, 0.0, ["pass", "pass", "fail", "pass"]),
    _t("admin_permission_allow", "tests_suite/test_admin.py::test_admin_require_permission_allows_role", "api", ["sample_app.admin", "sample_app.auth"], 0.06, 0.0, ["pass"] * 8, security=True),
    _t("admin_permission_deny", "tests_suite/test_admin.py::test_admin_require_permission_denies_role", "api", ["sample_app.admin", "sample_app.auth"], 0.06, 0.0, ["pass", "fail", "pass"], security=True),
    _t("reports_daily_revenue", "tests_suite/test_reports.py::test_daily_revenue_aggregation", "unit", ["sample_app.reports"], 0.06, 0.0, ["pass"] * 10),
    _t("reports_top_products", "tests_suite/test_reports.py::test_top_products_ranking", "unit", ["sample_app.reports"], 0.05, 0.0, ["pass"] * 10),
    _t("reports_empty_period", "tests_suite/test_reports.py::test_empty_period_report", "unit", ["sample_app.reports"], 0.05, 0.0, ["pass", "fail", "pass"]),
    _t("checkout_e2e_flow", "tests_suite/test_integration_checkout.py::test_end_to_end_checkout_flow", "integration", ["sample_app.orders", "sample_app.payments", "sample_app.customers"], 0.40, 0.0, ["pass"] * 6, security=True),
    _t("refund_e2e_ledger", "tests_suite/test_integration_checkout.py::test_refund_flow_adjusts_ledger", "integration", ["sample_app.payments", "sample_app.orders"], 0.38, 0.0, ["pass"] * 6, security=True),
    _t("contract_payments_orders", "tests_suite/test_contract_payments_orders.py::test_payment_contract_between_orders_and_payments", "contract", ["sample_app.payments", "sample_app.orders"], 0.30, 0.0, ["pass"] * 7, security=True),
    _t("smoke_critical_path", "tests_suite/test_smoke_critical_path.py::test_smoke_guest_to_receipt", "smoke", ["sample_app.auth", "sample_app.payments", "sample_app.orders"], 0.45, 0.0, ["pass"] * 20),
    _t("flaky_search_refresh", "tests_suite/test_flaky_seeded.py::test_flaky_search_index_refresh", "unit", ["sample_app.search"], 0.03, 0.5, ["pass", "fail", "pass", "fail", "pass", "pass"]),
    _t("flaky_auth_handshake", "tests_suite/test_flaky_seeded.py::test_flaky_auth_provider_handshake", "unit", ["sample_app.auth"], 0.03, 0.5, ["fail", "pass", "fail", "pass", "pass", "fail"]),
]


def seed(session: Session) -> None:
    for fields in MODULES:
        session.add(Module(**fields))
    for module, depends_on in DEPENDENCIES:
        session.add(CodeDependency(module=module, depends_on=depends_on, kind="import"))
    for fields in TEST_REGISTRY:
        session.add(TestRegistration(**fields))
    session.flush()
