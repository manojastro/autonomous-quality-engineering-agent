"""Reporting aggregations over completed orders."""
from __future__ import annotations

from typing import Dict, List

from sample_app.orders import ORDER_STATUS_COMPLETED


class ReportError(ValueError):
    """Raised for invalid report parameters."""


def daily_revenue(orders: List[dict]) -> Dict[str, float]:
    """Sum grand totals of completed orders grouped by ISO date."""
    totals: Dict[str, float] = {}
    for order in orders:
        if order.get("status") != ORDER_STATUS_COMPLETED:
            continue
        date = order["date"]
        totals[date] = round(totals.get(date, 0.0) + order["grand_total"], 2)
    return dict(sorted(totals.items()))


def top_products(order_lines: List[dict], limit: int = 3) -> List[dict]:
    """Rank products by quantity sold; ties broken by name ascending."""
    if limit < 1:
        raise ReportError("limit must be >= 1")
    counts: Dict[str, int] = {}
    names: Dict[str, str] = {}
    for line in order_lines:
        counts[line["sku"]] = counts.get(line["sku"], 0) + line["qty"]
        names.setdefault(line["sku"], line.get("name", line["sku"]))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], names[kv[0]]))
    return [{"sku": sku, "name": names[sku], "qty_sold": qty} for sku, qty in ranked[:limit]]


def summary_range(orders: List[dict], start: str, end: str) -> dict:
    """Inclusive-date revenue summary for completed orders."""
    if start > end:
        raise ReportError("start date must be <= end date")
    scoped = [o for o in orders if start <= o["date"] <= end and o.get("status") == ORDER_STATUS_COMPLETED]
    revenue = round(sum(o["grand_total"] for o in scoped), 2)
    return {"orders": len(scoped), "revenue": revenue, "average_order_value": round(revenue / len(scoped), 2) if scoped else 0.0}
