"""Contract pinning the payments interface consumed by orders."""
import pytest

from sample_app.payments import MAX_SINGLE_TRANSACTION, PaymentError, transaction_fee, validate_amount


def test_payment_contract_between_orders_and_payments() -> None:
    assert validate_amount(9999.99) == pytest.approx(9999.99)
    with pytest.raises(PaymentError):
        validate_amount(float(MAX_SINGLE_TRANSACTION) + 0.01)
    fee = transaction_fee(200.00)
    assert fee == pytest.approx(round(200.00 * 0.0175, 2))
    assert isinstance(fee, float)
