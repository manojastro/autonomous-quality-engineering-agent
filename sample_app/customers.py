"""Customer registry with tiered credit limits."""
from __future__ import annotations

from typing import Dict

CREDIT_LIMITS = {"BASIC": 1000.0, "SILVER": 5000.0, "GOLD": 20000.0}

_CUSTOMERS: Dict[int, dict] = {}
_NEXT_ID = 100


class CustomerError(ValueError):
    """Raised for invalid customer operations."""


def _validate_tier(tier: str) -> str:
    if tier not in CREDIT_LIMITS:
        raise CustomerError(f"unknown tier: {tier}")
    return tier


def register_customer(name: str, email: str, tier: str = "BASIC") -> dict:
    global _NEXT_ID
    if not name or not name.strip():
        raise CustomerError("name is required")
    if "@" not in email:
        raise CustomerError("valid email is required")
    _validate_tier(tier)
    customer = {
        "id": _NEXT_ID,
        "name": name.strip(),
        "email": email.strip().lower(),
        "tier": tier,
        "credit_limit": CREDIT_LIMITS[tier],
    }
    _CUSTOMERS[_NEXT_ID] = customer
    _NEXT_ID += 1
    return dict(customer)


def get_customer(customer_id: int) -> dict:
    if customer_id not in _CUSTOMERS:
        raise CustomerError(f"unknown customer id {customer_id}")
    return dict(_CUSTOMERS[customer_id])


def update_tier(customer_id: int, tier: str) -> dict:
    _validate_tier(tier)
    customer = get_customer(customer_id)
    customer["tier"] = tier
    customer["credit_limit"] = CREDIT_LIMITS[tier]
    _CUSTOMERS[customer_id] = customer
    return dict(customer)


def reset_customers() -> None:
    _CUSTOMERS.clear()
