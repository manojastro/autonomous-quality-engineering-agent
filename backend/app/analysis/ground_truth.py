"""Ground-truth labeled changes for selection evaluation."""
from __future__ import annotations

from typing import Any

LABELED_CASES: list[dict[str, Any]] = [
    {
        "name": "payments_validate_amount",
        "manifest": {
            "title": "Tighten payment validation",
            "files": [{"path": "sample_app/payments.py", "functions_changed": ["validate_amount"], "lines_added": 12, "lines_deleted": 3}],
        },
        "true_impacted_modules": ["sample_app.payments", "sample_app.orders", "sample_app.reports"],
    },
    {
        "name": "auth_token_expiry",
        "manifest": {
            "title": "Adjust token TTL handling",
            "files": [{"path": "sample_app/auth.py", "functions_changed": ["verify_token"], "lines_added": 8, "lines_deleted": 2}],
        },
        "true_impacted_modules": ["sample_app.auth", "sample_app.admin"],
    },
    {
        "name": "customers_tier_rules",
        "manifest": {
            "title": "Rework tier credit limits",
            "files": [{"path": "sample_app/customers.py", "functions_changed": ["update_tier"], "lines_added": 15, "lines_deleted": 6}],
        },
        "true_impacted_modules": ["sample_app.customers", "sample_app.orders", "sample_app.reports"],
    },
    {
        "name": "search_pagination",
        "manifest": {
            "title": "Fix pagination window math",
            "files": [{"path": "sample_app/search.py", "functions_changed": ["filter_products"], "lines_added": 9, "lines_deleted": 4}],
        },
        "true_impacted_modules": ["sample_app.search", "sample_app.orders", "sample_app.reports"],
    },
    {
        "name": "reports_summary_window",
        "manifest": {
            "title": "Extend summary range semantics",
            "files": [{"path": "sample_app/reports.py", "functions_changed": ["summary_range"], "lines_added": 7, "lines_deleted": 1}],
        },
        "true_impacted_modules": ["sample_app.reports"],
    },
    {
        "name": "admin_role_matrix",
        "manifest": {
            "title": "Add analyst report permission",
            "files": [{"path": "sample_app/admin.py", "functions_changed": ["require_permission"], "lines_added": 5, "lines_deleted": 1}],
        },
        "true_impacted_modules": ["sample_app.admin"],
    },
    {
        "name": "unrelated_docs_change",
        "manifest": {
            "title": "Update contributor docs",
            "files": [{"path": "docs/contributing.md", "functions_changed": [], "lines_added": 20, "lines_deleted": 2}],
        },
        "true_impacted_modules": [],
    },
]
