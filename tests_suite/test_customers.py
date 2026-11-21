import pytest

from sample_app import customers as cust
from sample_app.customers import CustomerError, get_customer, register_customer, update_tier


@pytest.fixture(autouse=True)
def _fresh() -> None:
    cust.reset_customers()


def test_register_customer_roundtrip() -> None:
    created = register_customer("Erin", "Erin@Example.com ", "SILVER")
    fetched = get_customer(created["id"])
    assert fetched["email"] == "erin@example.com"
    assert fetched["tier"] == "SILVER"


def test_credit_limit_by_tier() -> None:
    assert register_customer("Finn", "finn@example.com")["credit_limit"] == 1000.0
    gold = register_customer("Gina", "gina@example.com", "GOLD")
    assert gold["credit_limit"] == 20000.0
    assert update_tier(gold["id"], "BASIC")["credit_limit"] == 1000.0
    with pytest.raises(CustomerError):
        update_tier(gold["id"], "PLATINUM")
