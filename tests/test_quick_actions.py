"""Unit tests for quick_actions.py — the terse increase/decrease recommender."""

from __future__ import annotations

import pandas as pd
import pytest

from core import default_sales, default_stock, load_benchmarks
from quick_actions import (
    DIR_DECREASE,
    DIR_HOLD,
    DIR_INCREASE,
    QuickAction,
    quick_actions_df,
    quick_actions_to_csv,
)


COLUMNS = ["Action", "Product", "Adjust", "By", "Reason", "Priority"]


@pytest.fixture
def benchmarks() -> dict:
    return load_benchmarks()


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_quick_actions_df_returns_expected_columns(benchmarks):
    df = quick_actions_df(default_stock(), default_sales(), benchmarks)
    assert list(df.columns) == COLUMNS
    assert len(df) > 0, "default demo should produce at least one action"


def test_quick_actions_df_is_sorted_by_priority_desc(benchmarks):
    df = quick_actions_df(default_stock(), default_sales(), benchmarks)
    priorities = df["Priority"].tolist()
    assert priorities == sorted(priorities, reverse=True), (
        f"actions not sorted desc by priority: {priorities}"
    )


def test_empty_input_returns_empty_dataframe_with_columns(benchmarks):
    df = quick_actions_df(
        pd.DataFrame(columns=["Product", "Quantity"]),
        pd.DataFrame(columns=["Product", "Units Sold"]),
        benchmarks,
    )
    assert df.empty
    assert list(df.columns) == COLUMNS


# ---------------------------------------------------------------------------
# Direction labels (Increase / Decrease / Hold)
# ---------------------------------------------------------------------------


def test_direction_labels_have_icons():
    """The UI relies on each label starting with its emoji icon."""
    assert DIR_INCREASE.startswith("⬆️")
    assert DIR_DECREASE.startswith("⬇️")
    assert DIR_HOLD.startswith("⏸️")
    # Words must appear too — that was the user's whole request.
    assert "Increase" in DIR_INCREASE
    assert "Decrease" in DIR_DECREASE
    assert "Hold" in DIR_HOLD


# ---------------------------------------------------------------------------
# Action recognition
# ---------------------------------------------------------------------------


def test_sold_out_product_gets_increase_stock_at_max_priority(benchmarks):
    stock = pd.DataFrame([{"Product": "White bread loaf", "Quantity": 0}])
    sales = pd.DataFrame([{"Product": "White bread loaf", "Units Sold": 20}])
    df = quick_actions_df(stock, sales, benchmarks)

    top = df.iloc[0]
    assert top["Product"] == "White bread loaf"
    assert top["Action"] == DIR_INCREASE
    assert top["Adjust"] == "Stock"
    assert top["Priority"] == 100
    assert top["By"].startswith("+")
    assert "units" in top["By"]
    assert "sold out" in top["Reason"].lower()


def test_strong_sell_through_gets_increase_price(benchmarks):
    """Coca-Cola: 30 sold from a stock of 5 — top mover. Increase Price → R17."""
    stock = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Quantity": 5}])
    sales = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Units Sold": 30}])
    df = quick_actions_df(stock, sales, benchmarks)

    coke = df[df["Product"] == "Coca-Cola 500ml"]
    price_rows = coke[coke["Adjust"] == "Price"]
    assert not price_rows.empty
    price = price_rows.iloc[0]
    assert price["Action"] == DIR_INCREASE
    assert "R17" in price["By"]


def test_slow_mover_gets_decrease_price(benchmarks):
    """Sunlight: 30 stock, only 2 sold — slow. Decrease price to R12 (low end)."""
    stock = pd.DataFrame([{"Product": "Sunlight bar soap", "Quantity": 30}])
    sales = pd.DataFrame([{"Product": "Sunlight bar soap", "Units Sold": 2}])
    df = quick_actions_df(stock, sales, benchmarks)

    soap = df[df["Product"] == "Sunlight bar soap"]
    price_rows = soap[soap["Adjust"] == "Price"]
    assert not price_rows.empty
    price = price_rows.iloc[0]
    assert price["Action"] == DIR_DECREASE
    assert "R12" in price["By"]


def test_balanced_product_gets_hold_row(benchmarks):
    """No urgent restock, not a top mover, not a slow mover → Hold."""
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 50}])
    sales = pd.DataFrame([{"Product": "Niknaks 30g", "Units Sold": 25}])
    df = quick_actions_df(stock, sales, benchmarks)

    niknaks = df[df["Product"] == "Niknaks 30g"]
    assert not niknaks.empty
    hold = niknaks[niknaks["Action"] == DIR_HOLD]
    assert not hold.empty
    row = hold.iloc[0]
    assert row["Adjust"] == "—"
    assert row["By"] == "—"


def test_zero_sales_product_is_not_recommended_for_restock(benchmarks):
    """Stock sitting unsold → never trigger an Increase Stock action."""
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 50}])
    sales = pd.DataFrame([{"Product": "Niknaks 30g", "Units Sold": 0}])
    df = quick_actions_df(stock, sales, benchmarks)

    stock_rows = df[(df["Product"] == "Niknaks 30g") & (df["Adjust"] == "Stock")]
    assert stock_rows.empty


def test_product_with_no_benchmark_still_gets_a_row(benchmarks):
    """Unknown product names should still appear (with stock-side actions only)."""
    stock = pd.DataFrame([{"Product": "Some Mystery Brand", "Quantity": 0}])
    sales = pd.DataFrame([{"Product": "Some Mystery Brand", "Units Sold": 10}])
    df = quick_actions_df(stock, sales, benchmarks)

    rows = df[df["Product"] == "Some Mystery Brand"]
    assert not rows.empty
    # Stock-side Increase works without a benchmark; Price actions need one.
    adjustments = rows["Adjust"].tolist()
    assert "Stock" in adjustments
    assert "Price" not in adjustments


# ---------------------------------------------------------------------------
# QuickAction dataclass
# ---------------------------------------------------------------------------


def test_quick_action_as_row_has_expected_keys():
    qa = QuickAction(
        product="X",
        direction=DIR_INCREASE,
        adjust="Stock",
        by="+10 units",
        reason="sold out",
        priority=100,
    )
    row = qa.as_row()
    assert row == {
        "Action": DIR_INCREASE,
        "Product": "X",
        "Adjust": "Stock",
        "By": "+10 units",
        "Reason": "sold out",
        "Priority": 100,
    }


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_quick_actions_csv_has_expected_header(benchmarks):
    df = quick_actions_df(default_stock(), default_sales(), benchmarks)
    csv_bytes = quick_actions_to_csv(df)
    text = csv_bytes.decode("utf-8")
    first_line = text.splitlines()[0]
    assert first_line == "Action,Product,Adjust,By,Reason,Priority"


def test_quick_actions_csv_empty_input_safe(benchmarks):
    df = quick_actions_df(
        pd.DataFrame(columns=["Product", "Quantity"]),
        pd.DataFrame(columns=["Product", "Units Sold"]),
        benchmarks,
    )
    csv_bytes = quick_actions_to_csv(df)
    assert csv_bytes.decode("utf-8").startswith("Action,Product,Adjust,By,Reason,Priority")
