"""Unit tests for the pure-logic helpers in core.py."""

from __future__ import annotations

import pandas as pd
import pytest

from core import (
    Advice,
    benchmarks_by_name,
    default_sales,
    default_stock,
    load_benchmarks,
    parse_advice_response,
    total_units,
)


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_load_benchmarks_returns_expected_products():
    b = load_benchmarks()
    names = {p["name"] for p in b["products"]}
    expected = {
        "Niknaks 30g",
        "Simba chips 36g",
        "Coca-Cola 500ml",
        "Fanta 500ml",
        "White bread loaf",
        "Brown bread loaf",
        "Sunlight bar soap",
        "Lucky Star pilchards",
        "Maggi 2-min noodles",
        "Surf washing powder 500g",
    }
    assert expected.issubset(names)


def test_benchmarks_by_name_is_case_insensitive():
    b = load_benchmarks()
    idx = benchmarks_by_name(b)
    assert "niknaks 30g" in idx
    assert idx["niknaks 30g"]["median_price_rand"] == 7


def test_benchmark_price_ranges_are_sane():
    b = load_benchmarks()
    for p in b["products"]:
        lo, hi = p["price_range_rand"]
        assert lo > 0 and hi > lo, f"bad range for {p['name']}"
        assert lo <= p["median_price_rand"] <= hi


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


SAMPLE_RESPONSE = """## Restock this week
- White bread loaf: 30 loaves — you sold out last week.
- Coca-Cola 500ml: 24 bottles — top mover at R17.
- Niknaks 30g: 20 packets — steady demand.

## Pricing adjustments
- Lift Niknaks 30g from R6 to R7 (median is R7).
- Keep Coca-Cola at R17; right in the benchmark range.

## One product to add
Try Rama margarine 500g. Your bread sells fast and customers usually want
spread for it. Start with 6 tubs at R45 each.

*Confidence: High*
"""


def test_parse_advice_response_extracts_three_sections_and_confidence():
    advice = parse_advice_response(SAMPLE_RESPONSE)
    assert isinstance(advice, Advice)
    assert "White bread loaf" in advice.restock
    assert "Lift Niknaks" in advice.pricing
    assert "Rama margarine" in advice.add
    assert advice.confidence == "High"
    # Confidence line must not leak into the third section
    assert "Confidence" not in advice.add


def test_parse_advice_response_is_case_insensitive_for_headers():
    text = """## RESTOCK THIS WEEK
A
## Pricing Adjustments
B
## one product to add
C

*Confidence: Medium*
"""
    advice = parse_advice_response(text)
    assert advice.restock.strip() == "A"
    assert advice.pricing.strip() == "B"
    assert advice.add.strip() == "C"
    assert advice.confidence == "Medium"


def test_parse_advice_response_missing_sections_returns_empty_strings():
    text = "## Restock this week\nonly this section\n\n*Confidence: Low*"
    advice = parse_advice_response(text)
    assert advice.restock.strip() == "only this section"
    assert advice.pricing == ""
    assert advice.add == ""
    assert advice.confidence == "Low"


def test_parse_advice_response_handles_no_confidence_line():
    text = "## Restock this week\nA\n## Pricing adjustments\nB\n## One product to add\nC"
    advice = parse_advice_response(text)
    assert advice.confidence == "Unknown"


def test_parse_advice_response_empty_input():
    advice = parse_advice_response("")
    assert advice.restock == ""
    assert advice.pricing == ""
    assert advice.add == ""
    assert advice.confidence == "Unknown"


# ---------------------------------------------------------------------------
# total_units
# ---------------------------------------------------------------------------


def test_total_units_ignores_missing_and_blank_rows():
    df = pd.DataFrame(
        [
            {"Product": "A", "Quantity": 10},
            {"Product": "", "Quantity": 5},
            {"Product": "B", "Quantity": None},
        ]
    )
    assert total_units(df, "Quantity") == 10


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_stock_and_sales_have_five_rows_and_matching_products():
    stock = default_stock()
    sales = default_sales()
    assert len(stock) == 5
    assert len(sales) == 5
    assert set(stock["Product"]) == set(sales["Product"])


def test_default_stock_includes_a_sold_out_item():
    stock = default_stock()
    assert (stock["Quantity"] == 0).any(), "demo should show at least one sold-out row"


@pytest.mark.parametrize(
    "product",
    [
        "Niknaks 30g",
        "White bread loaf",
        "Coca-Cola 500ml",
        "Simba chips 36g",
        "Sunlight bar soap",
    ],
)
def test_each_default_product_has_a_benchmark(product):
    by = benchmarks_by_name(load_benchmarks())
    assert product.lower() in by
