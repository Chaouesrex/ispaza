"""Unit tests for tracker.py — purchase log + daily profit."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from core import load_benchmarks
from tracker import (
    Purchase,
    Sale,
    daily_profit_breakdown,
    default_purchase_log,
    default_sales_log,
    product_profit_breakdown,
    purchases_to_csv,
    purchases_to_df,
    running_totals,
    sales_to_csv,
    sales_to_df,
    total_cost_of_goods,
    total_profit,
    total_revenue,
    units_by_product,
    units_pivot_by_day,
)


# ---------------------------------------------------------------------------
# Dataclass behaviour
# ---------------------------------------------------------------------------


def test_purchase_total_cost_is_quantity_times_unit_cost():
    p = Purchase(date=date(2026, 5, 20), product="X", quantity=24, unit_cost_rand=10.5)
    assert p.total_cost_rand == 252.0


def test_sale_revenue_cost_and_profit_compute_correctly():
    s = Sale(
        date=date(2026, 5, 20),
        product="X",
        quantity=10,
        unit_price_rand=17.0,
        unit_cost_rand=10.0,
    )
    assert s.revenue_rand == 170.0
    assert s.cost_rand == 100.0
    assert s.profit_rand == 70.0


def test_sale_profit_rounds_to_cents():
    s = Sale(
        date=date(2026, 5, 20),
        product="X",
        quantity=3,
        unit_price_rand=4.99,
        unit_cost_rand=2.51,
    )
    # 3 * 4.99 = 14.97; 3 * 2.51 = 7.53; profit = 7.44
    assert s.profit_rand == 7.44


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------


def test_purchases_to_df_empty_returns_columns():
    df = purchases_to_df([])
    assert df.empty
    assert "Total Cost (R)" in df.columns


def test_purchases_to_df_sorts_by_date_then_product():
    purchases = [
        Purchase(date(2026, 5, 21), "B", 1, 5.0),
        Purchase(date(2026, 5, 20), "A", 1, 5.0),
        Purchase(date(2026, 5, 20), "B", 1, 5.0),
    ]
    df = purchases_to_df(purchases)
    assert df.iloc[0]["Product"] == "A"
    assert df.iloc[1]["Product"] == "B"
    assert df.iloc[2]["Date"] == "2026-05-21"


def test_sales_to_df_includes_revenue_cost_profit_columns():
    sales = [Sale(date(2026, 5, 20), "X", 10, 17.0, 10.0)]
    df = sales_to_df(sales)
    assert df.iloc[0]["Revenue (R)"] == 170.0
    assert df.iloc[0]["Cost (R)"] == 100.0
    assert df.iloc[0]["Profit (R)"] == 70.0


# ---------------------------------------------------------------------------
# Daily breakdown
# ---------------------------------------------------------------------------


def test_daily_profit_breakdown_sums_per_day():
    sales = [
        Sale(date(2026, 5, 20), "A", 2, 10.0, 5.0),  # rev 20 cost 10 profit 10
        Sale(date(2026, 5, 20), "B", 1, 20.0, 12.0),  # rev 20 cost 12 profit 8
        Sale(date(2026, 5, 21), "A", 3, 10.0, 5.0),  # rev 30 cost 15 profit 15
    ]
    daily = daily_profit_breakdown(sales)
    by_date = {row["Date"]: row for _, row in daily.iterrows()}

    assert by_date["2026-05-20"]["Revenue (R)"] == 40.0
    assert by_date["2026-05-20"]["Cost (R)"] == 22.0
    assert by_date["2026-05-20"]["Profit (R)"] == 18.0
    assert by_date["2026-05-21"]["Profit (R)"] == 15.0


def test_daily_profit_breakdown_computes_margin_percent():
    sales = [Sale(date(2026, 5, 20), "A", 10, 10.0, 6.0)]
    daily = daily_profit_breakdown(sales)
    # Profit 40 on revenue 100 → 40.0%
    assert daily.iloc[0]["Margin %"] == 40.0


def test_daily_profit_breakdown_empty_returns_columns():
    daily = daily_profit_breakdown([])
    assert daily.empty
    for col in ("Revenue (R)", "Cost (R)", "Profit (R)", "Units", "Margin %"):
        assert col in daily.columns


# ---------------------------------------------------------------------------
# Per-product breakdown
# ---------------------------------------------------------------------------


def test_product_profit_breakdown_ranks_by_profit_desc():
    sales = [
        Sale(date(2026, 5, 20), "Small", 1, 5.0, 4.0),     # profit 1
        Sale(date(2026, 5, 20), "Big", 10, 20.0, 10.0),    # profit 100
        Sale(date(2026, 5, 21), "Big", 5, 20.0, 10.0),     # profit 50
    ]
    per_product = product_profit_breakdown(sales)
    assert per_product.iloc[0]["Product"] == "Big"
    assert per_product.iloc[0]["Profit (R)"] == 150.0
    assert per_product.iloc[1]["Product"] == "Small"


def test_product_profit_breakdown_margin_handles_zero_revenue():
    # Edge case: a free sample sale (price 0, cost > 0) — margin should not crash.
    sales = [Sale(date(2026, 5, 20), "Free", 1, 0.0, 5.0)]
    per_product = product_profit_breakdown(sales)
    # Negative profit, undefined margin (we expect NaN, not a crash)
    assert per_product.iloc[0]["Profit (R)"] == -5.0


# ---------------------------------------------------------------------------
# Running totals
# ---------------------------------------------------------------------------


def test_running_totals_includes_cumulative_profit():
    sales = [
        Sale(date(2026, 5, 20), "A", 1, 10.0, 5.0),  # +5
        Sale(date(2026, 5, 21), "A", 1, 10.0, 5.0),  # +5 = 10
        Sale(date(2026, 5, 22), "A", 1, 10.0, 5.0),  # +5 = 15
    ]
    running = running_totals(sales)
    assert list(running["Cumulative Profit (R)"]) == [5.0, 10.0, 15.0]


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------


def test_total_profit_revenue_cost_helpers():
    sales = [
        Sale(date(2026, 5, 20), "A", 2, 10.0, 5.0),
        Sale(date(2026, 5, 21), "B", 3, 20.0, 12.0),
    ]
    assert total_revenue(sales) == 80.0
    assert total_cost_of_goods(sales) == 46.0
    assert total_profit(sales) == 34.0


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


def test_default_purchase_log_spans_two_weeks():
    today = date(2026, 5, 20)
    log = default_purchase_log(today=today, benchmarks=load_benchmarks())
    dates = {p.date for p in log}
    assert min(dates) >= today - timedelta(days=14)
    assert max(dates) <= today
    assert len(log) >= 10, "expect a meaty sample for the demo"


def test_default_purchase_log_uses_benchmark_cost_prices():
    today = date(2026, 5, 20)
    benchmarks = load_benchmarks()
    log = default_purchase_log(today=today, benchmarks=benchmarks)
    # Find a Coca-Cola purchase and check the unit cost is R10 (per benchmarks.json)
    cokes = [p for p in log if p.product == "Coca-Cola 500ml"]
    assert cokes, "expected some Coca-Cola purchases in the seed data"
    assert cokes[0].unit_cost_rand == 10.0


def test_default_purchase_log_attaches_supplier_metadata():
    today = date(2026, 5, 20)
    log = default_purchase_log(today=today, benchmarks=load_benchmarks())
    suppliers_used = {p.supplier for p in log}
    # Every seed purchase should have a supplier attached
    assert "" not in suppliers_used
    assert any("Sasko" in s for s in suppliers_used)


def test_default_sales_log_is_deterministic():
    today = date(2026, 5, 20)
    run_a = default_sales_log(today=today, benchmarks=load_benchmarks())
    run_b = default_sales_log(today=today, benchmarks=load_benchmarks())
    # Same seed → identical output
    assert [(s.date, s.product, s.quantity) for s in run_a] == [
        (s.date, s.product, s.quantity) for s in run_b
    ]


def test_default_sales_log_has_weekend_boost():
    today = date(2026, 5, 20)  # Wednesday
    sales = default_sales_log(today=today, benchmarks=load_benchmarks())
    # Friday is today-5 (May 15); Wednesday is today (May 20).
    fri = today - timedelta(days=5)
    wed = today
    fri_total = sum(s.quantity for s in sales if s.date == fri)
    wed_total = sum(s.quantity for s in sales if s.date == wed)
    # Both days should have sales, and the weekend day should outsell the midweek day.
    assert fri_total > 0 and wed_total > 0
    assert fri_total > wed_total, f"weekend boost not visible: Fri={fri_total} vs Wed={wed_total}"


def test_default_sales_log_yields_positive_total_profit():
    sales = default_sales_log(
        today=date(2026, 5, 20), benchmarks=load_benchmarks()
    )
    assert total_profit(sales) > 0


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Units charts
# ---------------------------------------------------------------------------


def test_units_by_product_ranks_descending():
    sales = [
        Sale(date(2026, 5, 20), "Big", 5, 10.0, 5.0),
        Sale(date(2026, 5, 21), "Big", 3, 10.0, 5.0),
        Sale(date(2026, 5, 20), "Small", 1, 5.0, 3.0),
    ]
    df = units_by_product(sales)
    assert list(df["Product"]) == ["Big", "Small"]
    assert list(df["Units"]) == [8, 1]


def test_units_by_product_empty_returns_columns():
    df = units_by_product([])
    assert df.empty
    assert list(df.columns) == ["Product", "Units"]


def test_units_pivot_by_day_has_product_columns_and_zero_fills():
    sales = [
        Sale(date(2026, 5, 20), "A", 3, 10.0, 5.0),
        Sale(date(2026, 5, 20), "B", 2, 10.0, 5.0),
        Sale(date(2026, 5, 21), "A", 4, 10.0, 5.0),
        # B not sold on the 21st — should appear as 0.
    ]
    pivot = units_pivot_by_day(sales)
    assert set(pivot.columns) == {"A", "B"}
    assert pivot.shape == (2, 2)
    # B on 2026-05-21 should be 0
    may21 = pivot.loc[pd.Timestamp("2026-05-21")]
    assert int(may21["A"]) == 4
    assert int(may21["B"]) == 0


def test_units_pivot_by_day_index_is_datetime_sorted():
    sales = [
        Sale(date(2026, 5, 22), "A", 1, 10.0, 5.0),
        Sale(date(2026, 5, 20), "A", 1, 10.0, 5.0),
        Sale(date(2026, 5, 21), "A", 1, 10.0, 5.0),
    ]
    pivot = units_pivot_by_day(sales)
    assert pivot.index.tolist() == sorted(pivot.index.tolist())


def test_units_pivot_by_day_empty_input_returns_empty_df():
    pivot = units_pivot_by_day([])
    assert pivot.empty


def test_purchases_csv_has_header_and_one_row_per_purchase():
    purchases = [
        Purchase(date(2026, 5, 20), "A", 1, 5.0, "Supplier X"),
        Purchase(date(2026, 5, 21), "B", 2, 7.5, "Supplier Y"),
    ]
    csv = purchases_to_csv(purchases).decode("utf-8")
    lines = csv.strip().splitlines()
    assert len(lines) == 3  # header + 2 rows
    assert "Supplier" in lines[0]


def test_sales_csv_has_profit_column():
    sales = [Sale(date(2026, 5, 20), "A", 2, 10.0, 5.0)]
    csv = sales_to_csv(sales).decode("utf-8")
    assert "Profit (R)" in csv.splitlines()[0]
