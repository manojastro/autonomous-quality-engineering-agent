import pytest

from sample_app.reports import ReportError, daily_revenue, summary_range, top_products


ORDERS = [
    {"order_id": "O1", "date": "2026-08-01", "grand_total": 125.61, "status": "completed"},
    {"order_id": "O2", "date": "2026-08-01", "grand_total": 74.39, "status": "completed"},
    {"order_id": "O3", "date": "2026-08-02", "grand_total": 300.00, "status": "refunded"},
    {"order_id": "O4", "date": "2026-08-03", "grand_total": 42.00, "status": "completed"},
]

LINES = [
    {"sku": "SKU-A", "name": "Keyboard", "qty": 3},
    {"sku": "SKU-B", "name": "Mouse", "qty": 5},
    {"sku": "SKU-A", "name": "Keyboard", "qty": 4},
]


def test_daily_revenue_aggregation() -> None:
    totals = daily_revenue(ORDERS)
    assert totals == {"2026-08-01": 200.0, "2026-08-03": 42.0}


def test_top_products_ranking() -> None:
    ranked = top_products(LINES, limit=2)
    assert ranked[0] == {"sku": "SKU-A", "name": "Keyboard", "qty_sold": 7}
    assert ranked[1]["sku"] == "SKU-B"


def test_empty_period_report() -> None:
    empty = summary_range(ORDERS, "2026-07-01", "2026-07-31")
    assert empty == {"orders": 0, "revenue": 0.0, "average_order_value": 0.0}
    window = summary_range(ORDERS, "2026-08-01", "2026-08-02")
    assert window["orders"] == 2 and window["revenue"] == 200.0
    with pytest.raises(ReportError):
        summary_range(ORDERS, "2026-08-05", "2026-08-01")
