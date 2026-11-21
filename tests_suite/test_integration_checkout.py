"""End-to-end flows spanning customers, orders, payments and search."""
import pytest

from sample_app import customers as cust
from sample_app import orders as orders_mod
from sample_app.search import PRICE_BOOK, filter_products
from sample_app.orders import checkout


@pytest.fixture(autouse=True)
def _fresh() -> None:
    cust.reset_customers()
    orders_mod.reset_orders()


def test_end_to_end_checkout_flow() -> None:
    cid = cust.register_customer("Hana", "hana@example.com", "SILVER")["id"]
    receipt = checkout(cid, [("SKU-A", 2), ("SKU-C", 3)])
    expected_subtotal = round(PRICE_BOOK["SKU-A"] * 2 + PRICE_BOOK["SKU-C"] * 3, 2)
    assert receipt["subtotal"] == pytest.approx(expected_subtotal)
    assert receipt["tier"] == "SILVER"
    assert receipt["discounted_subtotal"] == pytest.approx(130.24)
    assert receipt["fee"] == pytest.approx(2.28)
    assert receipt["grand_total"] == pytest.approx(132.52)
    affordable = filter_products([dict(sku="SKU-C", name="USB-C Cable", category="accessories", price=12.40)], max_price=20.0)
    assert affordable["total"] == 1


def test_refund_flow_adjusts_ledger() -> None:
    cid = cust.register_customer("Ivan", "ivan@example.com", "BASIC")["id"]
    receipt = checkout(cid, [("SKU-D", 1)])
    refund = orders_mod.process_refund(receipt["order_id"], 129.99)
    assert refund["net_refunded"] == pytest.approx(127.72)
    assert orders_mod.ledger_balance() == pytest.approx(receipt["grand_total"] - 127.72)
