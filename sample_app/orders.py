"""Order checkout, inventory reservation, refunds and recurring billing."""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Dict, List, Tuple

from sample_app.customers import CustomerError, get_customer
from sample_app.payments import PaymentError, refund_net_amount, transaction_fee, validate_amount
from sample_app.search import PRICE_BOOK

INVENTORY: Dict[str, int] = {"SKU-A": 25, "SKU-B": 40, "SKU-C": 100, "SKU-D": 8}

DISCOUNT_RATES = {"BASIC": 0.0, "SILVER": 0.05, "GOLD": 0.10}

ORDER_STATUS_COMPLETED = "completed"
ORDER_STATUS_REFUNDED = "refunded"

LEDGER: List[dict] = []
_ORDERS: Dict[str, dict] = {}
_ORDER_SEQ = 5000


class OrderError(ValueError):
    """Raised when an order cannot be placed."""


def check_inventory(sku: str, quantity: int) -> int:
    """Return remaining stock for a sku after reserving quantity."""
    if quantity < 1:
        raise OrderError("quantity must be >= 1")
    stock = INVENTORY.get(sku)
    if stock is None:
        raise OrderError(f"unknown sku {sku}")
    if stock < quantity:
        raise OrderError(f"insufficient inventory for {sku}: have {stock}, need {quantity}")
    INVENTORY[sku] = stock - quantity
    return INVENTORY[sku]


def apply_discount(subtotal: float, tier: str) -> float:
    """Apply the tier discount to a subtotal, half-even rounded to cents."""
    if tier not in DISCOUNT_RATES:
        raise OrderError(f"unknown tier {tier}")
    discounted = Decimal(str(subtotal)) * Decimal(str(1 - DISCOUNT_RATES[tier]))
    return float(discounted.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def _next_order_id() -> str:
    global _ORDER_SEQ
    _ORDER_SEQ += 1
    return f"ORD-{_ORDER_SEQ}"


def checkout(customer_id: int, items: List[Tuple[str, int]]) -> dict:
    """Run a full checkout: customer, inventory, pricing, fee and receipt."""
    customer = get_customer(customer_id)
    if not items:
        raise OrderError("cart is empty")
    lines: List[dict] = []
    subtotal = 0.0
    for sku, qty in items:
        unit = PRICE_BOOK.get(sku)
        if unit is None:
            raise OrderError(f"unknown sku {sku}")
        check_inventory(sku, qty)
        line_total = round(unit * qty, 2)
        subtotal += line_total
        lines.append({"sku": sku, "qty": qty, "unit_price": unit, "line_total": line_total})
    subtotal = round(subtotal, 2)
    discounted = apply_discount(subtotal, customer["tier"])
    try:
        fee = transaction_fee(discounted)
        validated_total = validate_amount(round(discounted + fee, 2))
    except PaymentError as exc:
        raise OrderError(f"payment rejected: {exc}") from exc
    order_id = _next_order_id()
    receipt = {
        "order_id": order_id,
        "customer_id": customer_id,
        "tier": customer["tier"],
        "lines": lines,
        "subtotal": subtotal,
        "discounted_subtotal": discounted,
        "fee": fee,
        "grand_total": validated_total,
        "status": ORDER_STATUS_COMPLETED,
    }
    _ORDERS[order_id] = receipt
    LEDGER.append({"kind": "charge", "order_id": order_id, "amount": validated_total})
    return dict(receipt)


def get_order(order_id: str) -> dict:
    if order_id not in _ORDERS:
        raise OrderError(f"unknown order {order_id}")
    return dict(_ORDERS[order_id])


def process_refund(order_id: str, amount: float) -> dict:
    """Refund part of a completed order; net amount excludes the fee."""
    order = get_order(order_id)
    if order["status"] == ORDER_STATUS_REFUNDED:
        raise OrderError("order already refunded")
    try:
        net = refund_net_amount(float(order["grand_total"]), amount)
    except PaymentError as exc:
        raise OrderError(f"refund rejected: {exc}") from exc
    order["status"] = ORDER_STATUS_REFUNDED
    LEDGER.append({"kind": "refund", "order_id": order_id, "amount": round(amount, 2), "net": net})
    return {"order_id": order_id, "refund_amount": round(amount, 2), "net_refunded": net, "status": ORDER_STATUS_REFUNDED}


def ledger_balance() -> float:
    balance = 0.0
    for entry in LEDGER:
        if entry["kind"] == "charge":
            balance += entry["amount"]
        else:
            balance -= entry["net"]
    return round(balance, 2)


def start_recurring_billing(customer_id: int, monthly_amount: float, cycles: int) -> dict:
    """Schedule a recurring billing plan priced through payments."""
    get_customer(customer_id)
    from sample_app.payments import recurring_cycle_total

    total = recurring_cycle_total(monthly_amount, cycles)
    return {"customer_id": customer_id, "monthly_amount": monthly_amount, "cycles": cycles, "cycle_total": total}


def reset_orders() -> None:
    global _ORDER_SEQ
    LEDGER.clear()
    _ORDERS.clear()
    _ORDER_SEQ = 5000
    INVENTORY.update({"SKU-A": 25, "SKU-B": 40, "SKU-C": 100, "SKU-D": 8})
