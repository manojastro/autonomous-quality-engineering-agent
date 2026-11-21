import pytest

from sample_app.search import SearchError, filter_products
from sample_app.search import PRODUCT_CATALOG as CATALOG


def test_filter_by_category() -> None:
    result = filter_products(CATALOG, category="peripherals")
    assert result["total"] == 2
    assert {item["sku"] for item in result["items"]} == {"SKU-A", "SKU-B"}


def test_price_range_filter() -> None:
    result = filter_products(CATALOG, max_price=50.0)
    assert result["total"] == 3
    assert all(item["price"] <= 50.0 for item in result["items"])
    with pytest.raises(SearchError):
        filter_products(CATALOG, max_price=-1)


def test_pagination_window() -> None:
    result = filter_products(CATALOG, page=2, page_size=2)
    assert result["pages"] == 2
    assert len(result["items"]) == 2
    with pytest.raises(SearchError):
        filter_products(CATALOG, page=0)
