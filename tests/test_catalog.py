"""Unit tests for catalog.py — the product browser."""

from __future__ import annotations

import pandas as pd
import pytest

from catalog import (
    CATALOG_COLUMNS,
    add_to_stock,
    catalog_df,
    filter_catalog,
    list_categories,
)
from core import load_benchmarks


@pytest.fixture
def benchmarks() -> dict:
    return load_benchmarks()


# ---------------------------------------------------------------------------
# catalog_df
# ---------------------------------------------------------------------------


def test_catalog_df_lists_every_product(benchmarks):
    df = catalog_df(benchmarks)
    assert len(df) == len(benchmarks["products"])
    assert list(df.columns) == CATALOG_COLUMNS


def test_catalog_df_includes_added_products(benchmarks):
    df = catalog_df(benchmarks)
    names = set(df["Product"])
    # The 7 products added in this iteration should all be present
    expected = {
        "Cadbury Lunch Bar 48g",
        "Oros 2L cordial",
        "Rama margarine 500g",
        "Iwisa maize meal 2.5kg",
        "Tastic rice 1kg",
        "Joko tea bags 100s",
        "Toilet rolls 6pk",
    }
    assert expected.issubset(names)


def test_catalog_df_computes_margin_percent(benchmarks):
    df = catalog_df(benchmarks)
    # Coca-Cola: cost R10, median R17 — margin = (17-10)/17 ≈ 41.2%
    coke = df[df["Product"] == "Coca-Cola 500ml"].iloc[0]
    assert coke["Cost (R)"] == 10.0
    assert coke["Median price (R)"] == 17.0
    assert coke["Margin %"] == pytest.approx(41.2, abs=0.1)


def test_catalog_df_renders_range_in_rand(benchmarks):
    df = catalog_df(benchmarks)
    niknaks = df[df["Product"] == "Niknaks 30g"].iloc[0]
    assert niknaks["Range (R)"] == "R5–R8"


def test_catalog_df_empty_returns_columns():
    df = catalog_df({"products": []})
    assert df.empty
    assert list(df.columns) == CATALOG_COLUMNS


# ---------------------------------------------------------------------------
# list_categories
# ---------------------------------------------------------------------------


def test_list_categories_is_sorted_and_unique(benchmarks):
    cats = list_categories(benchmarks)
    assert cats == sorted(cats)
    assert len(cats) == len(set(cats))
    # Sanity: at least the core categories show up
    assert "snacks" in cats
    assert "soft drinks" in cats
    assert "staples" in cats


# ---------------------------------------------------------------------------
# filter_catalog
# ---------------------------------------------------------------------------


def test_filter_catalog_query_matches_product_name(benchmarks):
    df = catalog_df(benchmarks)
    result = filter_catalog(df, query="bread")
    assert not result.empty
    assert all("bread" in name.lower() for name in result["Product"])


def test_filter_catalog_query_matches_supplier(benchmarks):
    df = catalog_df(benchmarks)
    result = filter_catalog(df, query="coca-cola")
    suppliers = result["Supplier"].tolist()
    products = result["Product"].tolist()
    # The query should match BOTH the Coca-Cola SA depot supplier rows AND
    # the Coca-Cola 500ml product row.
    assert any("Coca-Cola" in s for s in suppliers)
    assert any("Coca-Cola" in p for p in products)


def test_filter_catalog_is_case_insensitive(benchmarks):
    df = catalog_df(benchmarks)
    lower = filter_catalog(df, query="NIKNAKS")
    assert any(name == "Niknaks 30g" for name in lower["Product"])


def test_filter_catalog_by_category(benchmarks):
    df = catalog_df(benchmarks)
    result = filter_catalog(df, categories=["snacks"])
    assert not result.empty
    assert (result["Category"] == "snacks").all()


def test_filter_catalog_combines_query_and_category_with_and(benchmarks):
    df = catalog_df(benchmarks)
    # 'Niknaks' is a snack — combo hits.
    hit = filter_catalog(df, query="Niknaks", categories=["snacks"])
    assert len(hit) == 1
    # 'Niknaks' is NOT a household item — combo misses.
    miss = filter_catalog(df, query="Niknaks", categories=["household"])
    assert miss.empty


def test_filter_catalog_empty_filters_returns_all(benchmarks):
    df = catalog_df(benchmarks)
    result = filter_catalog(df)
    assert len(result) == len(df)
    result = filter_catalog(df, query="   ", categories=[])
    assert len(result) == len(df)


def test_filter_catalog_no_match_returns_empty(benchmarks):
    df = catalog_df(benchmarks)
    result = filter_catalog(df, query="zzz-nothing-zzz")
    assert result.empty


# ---------------------------------------------------------------------------
# add_to_stock
# ---------------------------------------------------------------------------


def test_add_to_stock_appends_new_product():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    out = add_to_stock(stock, "Coca-Cola 500ml", 12)
    assert len(out) == 2
    coke = out[out["Product"] == "Coca-Cola 500ml"].iloc[0]
    assert int(coke["Quantity"]) == 12


def test_add_to_stock_increments_existing_product():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    out = add_to_stock(stock, "Niknaks 30g", 7)
    assert len(out) == 1
    assert int(out.iloc[0]["Quantity"]) == 12


def test_add_to_stock_is_case_insensitive():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    out = add_to_stock(stock, "  NIKNAKS 30G  ", 3)
    assert len(out) == 1
    assert int(out.iloc[0]["Quantity"]) == 8


def test_add_to_stock_does_not_mutate_input():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    add_to_stock(stock, "Niknaks 30g", 10)
    assert int(stock.iloc[0]["Quantity"]) == 5


def test_add_to_stock_ignores_blank_product():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    out = add_to_stock(stock, "", 10)
    pd.testing.assert_frame_equal(out, stock)
    out = add_to_stock(stock, "   ", 10)
    pd.testing.assert_frame_equal(out, stock)


def test_add_to_stock_clamps_negative_quantity_to_zero():
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 5}])
    out = add_to_stock(stock, "Coca-Cola 500ml", -3)
    coke = out[out["Product"] == "Coca-Cola 500ml"].iloc[0]
    assert int(coke["Quantity"]) == 0


def test_add_to_stock_handles_empty_input_df():
    empty = pd.DataFrame(columns=["Product", "Quantity"])
    out = add_to_stock(empty, "Niknaks 30g", 5)
    assert len(out) == 1
    assert out.iloc[0]["Product"] == "Niknaks 30g"
    assert int(out.iloc[0]["Quantity"]) == 5
