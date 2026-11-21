"""Critical-path smoke: guest catalog view through a paid receipt."""
from sample_app import customers as cust
from sample_app import orders as orders_mod
from sample_app.orders import checkout
from sample_app.search import filter_products, PRODUCT_CATALOG


def test_smoke_guest_to_receipt() -> None:
    results = filter_products(PRODUCT_CATALOG, category="accessories")
    sku = results["items"][0]["sku"]
    cust.reset_customers()
    orders_mod.reset_orders()
    cid = cust.register_customer("Smoke User", "smoke@example.com")["id"]
    receipt = checkout(cid, [(sku, 1)])
    assert receipt["status"] == "completed"
    assert receipt["grand_total"] > receipt["discounted_subtotal"]
