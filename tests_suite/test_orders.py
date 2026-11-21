import pytest

from sample_app import customers as cust
from sample_app.customers import CustomerError
from sample_app import orders as orders_mod
from sample_app.orders import OrderError, apply_discount, checkout, ledger_balance


@pytest.fixture(autouse=True)
def _fresh_state() -> None:
    cust.reset_customers()
    orders_mod.reset_orders()


def _gold_customer() -> int:
    return cust.register_customer("Ada Gold", "ada@example.com", "GOLD")["id"]


def test_checkout_receipt_totals() -> None:
    cid = cust.register_customer("Bob", "bob@example.com", "BASIC")["id"]
    receipt = checkout(cid, [("SKU-A", 1), ("SKU-B", 2)])
    assert receipt["subtotal"] == pytest.approx(123.45)
    assert receipt["fee"] == pytest.approx(2.16)
    assert receipt["grand_total"] == pytest.approx(125.61)


def test_checkout_applies_gold_discount() -> None:
    cid = _gold_customer()
    receipt = checkout(cid, [("SKU-A", 1), ("SKU-B", 2)])
    assert receipt["discounted_subtotal"] == pytest.approx(111.10)
    assert receipt["fee"] == pytest.approx(1.94)
    assert receipt["grand_total"] == pytest.approx(113.04)
    assert apply_discount(100.00, "SILVER") == pytest.approx(95.00)


def test_checkout_rejects_insufficient_inventory() -> None:
    cid = cust.register_customer("Cara", "cara@example.com", "SILVER")["id"]
    with pytest.raises(OrderError):
        checkout(cid, [("SKU-D", 99)])
    assert ledger_balance() == 0.0


def test_checkout_requires_known_customer() -> None:
    with pytest.raises(CustomerError):
        checkout(999999, [("SKU-C", 1)])


def test_refund_flow_adjusts_ledger() -> None:
    cid = cust.register_customer("Dan", "dan@example.com", "BASIC")["id"]
    receipt = checkout(cid, [("SKU-A", 1), ("SKU-B", 2)])
    refund = orders_mod.process_refund(receipt["order_id"], 123.45)
    assert refund["net_refunded"] == pytest.approx(121.29)
    assert ledger_balance() == pytest.approx(125.61 - 121.29)
