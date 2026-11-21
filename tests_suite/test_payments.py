import pytest

from sample_app import payments as pay


def test_validate_amount_accepts_in_range() -> None:
    assert pay.validate_amount(250.00) == 250.00
    assert pay.validate_amount(10000.00) == 10000.00
    assert pay.validate_amount(0.01) == 0.01


def test_validate_amount_rejects_non_positive() -> None:
    with pytest.raises(pay.PaymentError):
        pay.validate_amount(0)
    with pytest.raises(pay.PaymentError):
        pay.validate_amount(-5.50)


def test_validate_amount_rejects_above_limit() -> None:
    with pytest.raises(pay.PaymentError):
        pay.validate_amount(10000.01)


def test_transaction_fee_uses_half_even_rounding() -> None:
    assert pay.transaction_fee(123.45) == pytest.approx(2.16)
    assert pay.transaction_fee(333.33) == pytest.approx(5.83)
    assert pay.transaction_fee(100.00) == pytest.approx(1.75)


def test_refund_net_amount_math() -> None:
    net = pay.refund_net_amount(original_amount=500.00, refund_amount=333.33)
    assert net == pytest.approx(327.50)


def test_recurring_cycle_totals() -> None:
    total = pay.recurring_cycle_total(monthly_amount=129.99, cycles=3)
    assert total == pytest.approx(396.78)
    with pytest.raises(pay.PaymentError):
        pay.recurring_cycle_total(10.00, 0)
