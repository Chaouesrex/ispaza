"""Purchase log + daily profit tracking.

Two simple dataclasses, ``Purchase`` and ``Sale``, and a handful of pure
helpers that turn lists of them into the DataFrames the UI charts and
tables consume:

* ``daily_profit_breakdown(sales)`` → one row per day with revenue, cost,
  profit, and margin. Drop straight into ``st.line_chart``.
* ``product_profit_breakdown(sales)`` → one row per product over the
  whole window. Lets the owner see which lines actually pay the rent.
* ``running_totals(sales)`` → the running-sum chart for the headline KPI.

Plus default seed data (``default_purchase_log`` / ``default_sales_log``)
so the demo has a believable 14-day story arc the moment the app loads —
without that, the chart is a flat line and nothing reads as real.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable

import numpy as np
import pandas as pd

from core import benchmarks_by_name


def _margin_pct(profit: pd.Series, revenue: pd.Series) -> pd.Series:
    """Margin % rounded to 1dp, NaN where revenue is zero (avoids 0/0)."""
    margin = np.where(revenue != 0, profit / revenue * 100, np.nan)
    return pd.Series(np.round(margin, 1), index=profit.index)


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Purchase:
    """One stock-in event: what arrived, when, and what it cost."""

    date: date
    product: str
    quantity: int
    unit_cost_rand: float
    supplier: str = ""

    @property
    def total_cost_rand(self) -> float:
        return round(self.quantity * self.unit_cost_rand, 2)


@dataclass(frozen=True)
class Sale:
    """One sale (aggregated per product per day in this demo).

    ``unit_cost_rand`` is captured at sale-time so historical profit is
    correct even if the wholesale price later changes.
    """

    date: date
    product: str
    quantity: int
    unit_price_rand: float
    unit_cost_rand: float

    @property
    def revenue_rand(self) -> float:
        return round(self.quantity * self.unit_price_rand, 2)

    @property
    def cost_rand(self) -> float:
        return round(self.quantity * self.unit_cost_rand, 2)

    @property
    def profit_rand(self) -> float:
        return round(self.revenue_rand - self.cost_rand, 2)


# ---------------------------------------------------------------------------
# DataFrame builders
# ---------------------------------------------------------------------------


def purchases_to_df(purchases: Iterable[Purchase]) -> pd.DataFrame:
    rows = [
        {
            "Date": p.date.isoformat(),
            "Product": p.product,
            "Quantity": p.quantity,
            "Unit Cost (R)": round(p.unit_cost_rand, 2),
            "Total Cost (R)": p.total_cost_rand,
            "Supplier": p.supplier,
        }
        for p in purchases
    ]
    if not rows:
        return pd.DataFrame(
            columns=["Date", "Product", "Quantity", "Unit Cost (R)", "Total Cost (R)", "Supplier"]
        )
    return pd.DataFrame(rows).sort_values(["Date", "Product"]).reset_index(drop=True)


def sales_to_df(sales: Iterable[Sale]) -> pd.DataFrame:
    rows = [
        {
            "Date": s.date.isoformat(),
            "Product": s.product,
            "Units": s.quantity,
            "Unit Price (R)": round(s.unit_price_rand, 2),
            "Unit Cost (R)": round(s.unit_cost_rand, 2),
            "Revenue (R)": s.revenue_rand,
            "Cost (R)": s.cost_rand,
            "Profit (R)": s.profit_rand,
        }
        for s in sales
    ]
    if not rows:
        return pd.DataFrame(
            columns=[
                "Date", "Product", "Units",
                "Unit Price (R)", "Unit Cost (R)",
                "Revenue (R)", "Cost (R)", "Profit (R)",
            ]
        )
    return pd.DataFrame(rows).sort_values(["Date", "Product"]).reset_index(drop=True)


def daily_profit_breakdown(sales: Iterable[Sale]) -> pd.DataFrame:
    """One row per day. Columns: Revenue, Cost, Profit, Units, Margin %.

    Days with no recorded sales do not appear; the caller can reindex
    onto a full date range if it wants a gapless chart.
    """
    df = sales_to_df(sales)
    if df.empty:
        return pd.DataFrame(columns=["Date", "Revenue (R)", "Cost (R)", "Profit (R)", "Units", "Margin %"])

    daily = (
        df.groupby("Date", as_index=False)
        .agg(
            **{
                "Revenue (R)": ("Revenue (R)", "sum"),
                "Cost (R)": ("Cost (R)", "sum"),
                "Profit (R)": ("Profit (R)", "sum"),
                "Units": ("Units", "sum"),
            }
        )
        .sort_values("Date")
        .reset_index(drop=True)
    )
    daily["Margin %"] = _margin_pct(daily["Profit (R)"], daily["Revenue (R)"])
    return daily


def product_profit_breakdown(sales: Iterable[Sale]) -> pd.DataFrame:
    """One row per product over the whole window — ranked by profit desc."""
    df = sales_to_df(sales)
    if df.empty:
        return pd.DataFrame(columns=["Product", "Units", "Revenue (R)", "Cost (R)", "Profit (R)", "Margin %"])

    per_product = (
        df.groupby("Product", as_index=False)
        .agg(
            **{
                "Units": ("Units", "sum"),
                "Revenue (R)": ("Revenue (R)", "sum"),
                "Cost (R)": ("Cost (R)", "sum"),
                "Profit (R)": ("Profit (R)", "sum"),
            }
        )
        .sort_values("Profit (R)", ascending=False)
        .reset_index(drop=True)
    )
    per_product["Margin %"] = _margin_pct(
        per_product["Profit (R)"], per_product["Revenue (R)"]
    )
    return per_product


def running_totals(sales: Iterable[Sale]) -> pd.DataFrame:
    """Daily breakdown with a Cumulative Profit column. Use for the headline chart."""
    daily = daily_profit_breakdown(sales)
    if daily.empty:
        return daily
    daily = daily.copy()
    daily["Cumulative Profit (R)"] = daily["Profit (R)"].cumsum().round(2)
    return daily


def units_by_product(sales: Iterable[Sale]) -> pd.DataFrame:
    """Total units sold per product over the whole window, sorted desc.

    DataFrame with two columns: ``Product`` and ``Units``. Drop straight
    into ``st.bar_chart`` after setting Product as the index.
    """
    df = sales_to_df(sales)
    if df.empty:
        return pd.DataFrame(columns=["Product", "Units"])
    return (
        df.groupby("Product", as_index=False)["Units"]
        .sum()
        .sort_values("Units", ascending=False)
        .reset_index(drop=True)
    )


def units_pivot_by_day(sales: Iterable[Sale]) -> pd.DataFrame:
    """Day × Product pivot of units sold. Use for the stacked bar chart.

    Index = ``pd.Timestamp`` per date, columns = product names, values =
    units sold (0 where the product wasn't sold that day).
    """
    df = sales_to_df(sales)
    if df.empty:
        return pd.DataFrame()
    pivot = df.pivot_table(
        index="Date",
        columns="Product",
        values="Units",
        aggfunc="sum",
        fill_value=0,
    )
    pivot.index = pd.to_datetime(pivot.index)
    pivot = pivot.sort_index()
    return pivot


def total_profit(sales: Iterable[Sale]) -> float:
    return round(sum(s.profit_rand for s in sales), 2)


def total_revenue(sales: Iterable[Sale]) -> float:
    return round(sum(s.revenue_rand for s in sales), 2)


def total_cost_of_goods(sales: Iterable[Sale]) -> float:
    return round(sum(s.cost_rand for s in sales), 2)


# ---------------------------------------------------------------------------
# Seed data — 14-day plausible window so the demo loads with a story
# ---------------------------------------------------------------------------


_DAILY_SALES_PROFILE: dict[str, tuple[int, int]] = {
    # product -> (min units/day, max units/day) when in stock
    "Niknaks 30g": (2, 5),
    "Simba chips 36g": (1, 3),
    "Coca-Cola 500ml": (3, 6),
    "Fanta 500ml": (1, 3),
    "White bread loaf": (3, 7),
    "Brown bread loaf": (1, 3),
    "Sunlight bar soap": (0, 1),
    "Lucky Star pilchards": (0, 2),
    "Maggi 2-min noodles": (4, 9),
}


def default_purchase_log(
    today: date | None = None,
    benchmarks: dict[str, Any] | None = None,
) -> list[Purchase]:
    """Plausible last-14-days purchase history matching the default sales arc."""
    today = today or date.today()
    if benchmarks is None:
        from core import load_benchmarks

        benchmarks = load_benchmarks()
    idx = benchmarks_by_name(benchmarks)

    plan: list[tuple[int, str, int]] = [
        # (days_ago, product, units bought)
        (13, "White bread loaf", 30),
        (13, "Coca-Cola 500ml", 24),
        (12, "Maggi 2-min noodles", 60),
        (11, "White bread loaf", 30),
        (10, "Niknaks 30g", 24),
        (10, "Simba chips 36g", 24),
        (9, "White bread loaf", 30),
        (8, "Fanta 500ml", 24),
        (7, "Lucky Star pilchards", 12),
        (6, "Sunlight bar soap", 12),
        (6, "White bread loaf", 35),
        (5, "Coca-Cola 500ml", 24),
        (4, "White bread loaf", 30),
        (3, "Niknaks 30g", 24),
        (1, "White bread loaf", 35),
    ]
    log: list[Purchase] = []
    for days_ago, name, qty in plan:
        bench = idx.get(name.lower())
        if not bench:
            continue
        log.append(
            Purchase(
                date=today - timedelta(days=days_ago),
                product=name,
                quantity=qty,
                unit_cost_rand=float(bench["cost_price_rand"]),
                supplier=bench.get("supplier", ""),
            )
        )
    return log


def default_sales_log(
    today: date | None = None,
    benchmarks: dict[str, Any] | None = None,
) -> list[Sale]:
    """Plausible last-14-days sales — deterministic, profile-driven."""
    today = today or date.today()
    if benchmarks is None:
        from core import load_benchmarks

        benchmarks = load_benchmarks()
    idx = benchmarks_by_name(benchmarks)

    rng = random.Random(20260520)  # deterministic for the demo
    sales: list[Sale] = []
    for days_ago in range(13, -1, -1):
        d = today - timedelta(days=days_ago)
        # Weekend boost (Fri/Sat) — typical for spaza foot traffic.
        weekend_boost = 1.6 if d.weekday() in (4, 5) else 1.0
        for name, (lo, hi) in _DAILY_SALES_PROFILE.items():
            bench = idx.get(name.lower())
            if not bench:
                continue
            base = rng.randint(lo, hi)
            qty = int(round(base * weekend_boost))
            if qty <= 0:
                continue
            sales.append(
                Sale(
                    date=d,
                    product=name,
                    quantity=qty,
                    unit_price_rand=float(bench["median_price_rand"]),
                    unit_cost_rand=float(bench["cost_price_rand"]),
                )
            )
    return sales


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------


def purchases_to_csv(purchases: Iterable[Purchase]) -> bytes:
    return purchases_to_df(purchases).to_csv(index=False).encode("utf-8")


def sales_to_csv(sales: Iterable[Sale]) -> bytes:
    return sales_to_df(sales).to_csv(index=False).encode("utf-8")
