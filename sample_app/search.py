"""Product catalog and search filters."""
from __future__ import annotations

import math
from typing import Iterable, List, Optional

PRICE_BOOK = {
    "SKU-A": 49.95,
    "SKU-B": 36.75,
    "SKU-C": 12.40,
    "SKU-D": 129.99,
}

PRODUCT_CATALOG: List[dict] = [
    {"sku": "SKU-A", "name": "Mechanical Keyboard", "category": "peripherals", "price": 49.95},
    {"sku": "SKU-B", "name": "Wireless Mouse", "category": "peripherals", "price": 36.75},
    {"sku": "SKU-C", "name": "USB-C Cable", "category": "accessories", "price": 12.40},
    {"sku": "SKU-D", "name": "UltraWide Monitor", "category": "displays", "price": 129.99},
]


class SearchError(ValueError):
    """Raised for invalid search parameters."""


def filter_products(
    products: List[dict],
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    query: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """Filter, full-text match and paginate a product list."""
    if page < 1 or page_size < 1:
        raise SearchError("page and page_size must be >= 1")
    items: List[dict] = list(products)
    if category is not None:
        items = [p for p in items if p["category"] == category]
    if max_price is not None:
        if max_price < 0:
            raise SearchError("max_price must be >= 0")
        items = [p for p in items if p["price"] <= max_price]
    if query is not None:
        needle = query.lower()
        items = [p for p in items if needle in p["name"].lower()]
    total = len(items)
    pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    return {"items": items[start : start + page_size], "total": total, "page": page, "pages": pages}


def iter_catalog() -> Iterable[dict]:
    return iter(PRODUCT_CATALOG)
