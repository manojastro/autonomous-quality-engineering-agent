"""Payment primitives.

Contains the QE_BUG_PAYMENTS regression injection point used by the quality
engineering agent to produce genuine failing behaviour during demos.
"""
from __future__ import annotations

import logging
import os
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Dict

logger = logging.getLogger("sample_app.payments")

MAX_SINGLE_TRANSACTION = Decimal("10000.00")

_BUG_STATE_FILE = Path(__file__).with_name(".qe_bug_payments")

TRANSACTION_LOG: Dict[str, Dict[str, float]] = {}


class PaymentError(ValueError):
    """Raised when a payment amount or operation is invalid."""


class RefundError(PaymentError):
    """Raised when a refund cannot be applied."""


def bug_active() -> bool:
    if os.environ.get("QE_BUG_PAYMENTS") == "1":
        return True
    try:
        return _BUG_STATE_FILE.exists()
    except OSError:
        return False


def set_bug_state(active: bool) -> bool:
    try:
        if active:
            _BUG_STATE_FILE.write_text("payments.validate_amount+transaction_fee off-by-one/rounding\n", encoding="utf-8")
        elif _BUG_STATE_FILE.exists():
            _BUG_STATE_FILE.unlink()
    except OSError:
        logger.warning("could not persist payments regression state")
    return bug_active()


def _quantize(value: Decimal, rounding: str) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=rounding)


def validate_amount(amount: float) -> float:
    """Validate a transaction amount and return the normalized value."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise PaymentError("amount must be numeric")
    amt = _quantize(Decimal(str(float(amount))), ROUND_HALF_EVEN)
    if amt <= 0:
        raise PaymentError("amount must be positive")
    upper = MAX_SINGLE_TRANSACTION + (Decimal("1.00") if bug_active() else Decimal("0.00"))
    if amt > upper:
        raise PaymentError(f"amount exceeds single transaction limit {MAX_SINGLE_TRANSACTION}")
    return float(amt)


def transaction_fee(amount: float) -> float:
    """Flat 1.75% processing fee, half-even rounded to cents."""
    amt = Decimal(str(validate_amount(amount)))
    raw_fee = amt * Decimal("0.0175")
    fee = _quantize(raw_fee, ROUND_CEILING if bug_active() else ROUND_HALF_EVEN)
    logger.info("fee computed amount=%s fee=%s", amt, fee)
    return float(fee)


def charge(order_id: str, amount: float) -> Dict[str, float]:
    validated = validate_amount(amount)
    fee = transaction_fee(validated)
    record = {"order_id": order_id, "amount": validated, "fee": fee, "charged_total": round(validated + fee, 2)}
    TRANSACTION_LOG[order_id] = record
    return record


def refund_net_amount(original_amount: float, refund_amount: float) -> float:
    """Net refund equals refund minus its non-refundable processing fee."""
    original = Decimal(str(validate_amount(original_amount)))
    refunded = Decimal(str(validate_amount(refund_amount)))
    if refunded > original:
        raise RefundError("refund exceeds original charge")
    fee = Decimal(str(transaction_fee(float(refunded))))
    return float((refunded - fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def recurring_cycle_total(monthly_amount: float, cycles: int) -> float:
    """Total charged across a recurring billing cycle including per-cycle fees."""
    if cycles < 1:
        raise PaymentError("cycles must be >= 1")
    total = Decimal("0.00")
    for _ in range(cycles):
        total += Decimal(str(monthly_amount)) + Decimal(str(transaction_fee(monthly_amount)))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def reset_payments() -> None:
    TRANSACTION_LOG.clear()
