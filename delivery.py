"""Delivery scheduling and optimal purchase-day planning.

The data in ``data/benchmarks.json`` and ``data/suppliers.json`` encodes
realistic SA-township sourcing patterns: bread routes that run six days
a week, the Coca-Cola depot's twice-weekly truck, the Simba rep's single
Wednesday window, and the cash-and-carry trip the owner makes for
everything else.

This module turns that data into three concrete views the UI renders:

* ``weekly_schedule`` — Mon→Sun grid of what's arriving and what to
  order today. Pure data — no opinions about urgency.
* ``upcoming_deliveries`` — same grid but anchored to real dates, so
  "Tuesday" becomes "Tue 21 May".
* ``purchase_plan`` — opinions, finally. Looks at the owner's actual
  stock and sales, decides what they need to source this week, then
  buckets the orders by supplier and best purchase day.

The plan view is the headline: it answers "which day should I be where,
spending money on what?" — a question every spaza owner has to solve
every week.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterable

import pandas as pd

from advisor import _build_signals, _ProductSignal, _round_order
from core import DAYS_OF_WEEK, benchmarks_by_name, clean_df, load_suppliers, suppliers_by_name


# ---------------------------------------------------------------------------
# Static views — Mon→Sun grid
# ---------------------------------------------------------------------------


def weekly_schedule(
    benchmarks: dict[str, Any],
    products_in_shop: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Mon→Sun grid showing what's arriving each day and what to order.

    ``products_in_shop`` filters the grid to a specific shop's mix. Pass
    ``None`` to see the full reference schedule.
    """
    catalogue = benchmarks.get("products", [])
    if products_in_shop is not None:
        wanted = {p.strip().lower() for p in products_in_shop if isinstance(p, str)}
        catalogue = [p for p in catalogue if p["name"].lower() in wanted]

    arrivals: dict[str, list[str]] = {d: [] for d in DAYS_OF_WEEK}
    orders: dict[str, list[str]] = {d: [] for d in DAYS_OF_WEEK}

    for product in catalogue:
        name = product["name"]
        for day in product.get("delivery_days", []):
            if day in arrivals:
                arrivals[day].append(name)
        order_day = product.get("best_purchase_day")
        if order_day and order_day in orders:
            orders[order_day].append(name)

    rows = []
    for day in DAYS_OF_WEEK:
        rows.append(
            {
                "Day": day,
                "Deliveries arriving": ", ".join(sorted(set(arrivals[day]))) or "—",
                "Best to order / buy": ", ".join(sorted(set(orders[day]))) or "—",
            }
        )
    return pd.DataFrame(rows)


def upcoming_deliveries(
    today: date,
    benchmarks: dict[str, Any],
    products_in_shop: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Next-7-days calendar with concrete dates.

    Returned DataFrame has columns: ``Date``, ``Day``, ``Deliveries arriving``,
    ``Best to order / buy``. Today appears first.
    """
    schedule = weekly_schedule(benchmarks, products_in_shop=products_in_shop)
    schedule_by_day = {row["Day"]: row for _, row in schedule.iterrows()}

    rows = []
    for offset in range(7):
        d = today + timedelta(days=offset)
        day_name = DAYS_OF_WEEK[d.weekday()]
        sched = schedule_by_day[day_name]
        rows.append(
            {
                "Date": d.isoformat(),
                "Day": day_name + (" (today)" if offset == 0 else ""),
                "Deliveries arriving": sched["Deliveries arriving"],
                "Best to order / buy": sched["Best to order / buy"],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Opinionated view — purchase plan tied to the owner's signals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PurchaseRecommendation:
    """One opinionated 'buy X units of Y from Z on day D' line."""

    product: str
    quantity: int
    supplier: str
    channel: str           # "direct_delivery" | "cash_and_carry"
    best_day: str          # Monday-Sunday
    next_date: date
    pack_size: int
    unit_cost_rand: float
    est_cost_rand: float
    urgency: int           # 0–100
    reason: str            # one-line reason

    def as_row(self) -> dict[str, Any]:
        return {
            "Product": self.product,
            "Buy": f"{self.quantity} units",
            "Unit cost (R)": round(self.unit_cost_rand, 2),
            "Est. cost (R)": round(self.est_cost_rand, 2),
            "Supplier": self.supplier,
            "Channel": self.channel.replace("_", " "),
            "Best day": self.best_day,
            "Next date": self.next_date.isoformat(),
            "Reason": self.reason,
            "Urgency": self.urgency,
        }


def _next_occurrence(today: date, day_name: str) -> date:
    """Next calendar date matching ``day_name`` (today counts)."""
    if day_name not in DAYS_OF_WEEK:
        return today
    target = DAYS_OF_WEEK.index(day_name)
    delta = (target - today.weekday()) % 7
    return today + timedelta(days=delta)


def _recommendation_for(
    s: _ProductSignal,
    bench: dict[str, Any],
    today: date,
) -> PurchaseRecommendation | None:
    """Decide whether to buy and bundle the operational details."""
    if s.sold == 0:
        return None

    if s.stock == 0:
        qty = _round_order(max(int(s.sold * 1.5), 6))
        urgency = 100
        reason = f"sold out after {s.sold} sold last week"
    elif s.weeks_left < 1:
        qty = _round_order(max(int(s.sold * 1.4), 6))
        urgency = 80
        reason = f"only {s.stock} left vs {s.sold} sold — under a week of cover"
    elif s.sell_through >= 0.5 and s.sold >= 6:
        qty = _round_order(max(int(s.sold * 1.2), 6))
        urgency = 60
        reason = f"{int(s.sell_through * 100)}% sell-through — top up before the weekend"
    elif s.weeks_left < 2:
        qty = _round_order(max(s.sold, 5))
        urgency = 40
        reason = "around a week and a half of cover — reorder to stay ahead"
    else:
        return None

    pack_size = int(bench.get("wholesale_pack_size", 1) or 1)
    # Round the quantity up to the nearest full pack — owners don't break boxes.
    if pack_size > 1:
        qty = ((qty + pack_size - 1) // pack_size) * pack_size

    cost_each = float(bench.get("cost_price_rand", 0) or 0)
    est_cost = round(qty * cost_each, 2)
    best_day = bench.get("best_purchase_day") or "Tuesday"
    supplier = bench.get("supplier", "—")
    channel = "cash_and_carry" if "cash" in supplier.lower() else "direct_delivery"

    return PurchaseRecommendation(
        product=s.name,
        quantity=qty,
        supplier=supplier,
        channel=channel,
        best_day=best_day,
        next_date=_next_occurrence(today, best_day),
        pack_size=pack_size,
        unit_cost_rand=cost_each,
        est_cost_rand=est_cost,
        urgency=urgency,
        reason=reason,
    )


def purchase_plan(
    stock_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    benchmarks: dict[str, Any],
    today: date | None = None,
) -> pd.DataFrame:
    """Owner-facing weekly purchase plan: what to buy where and when."""
    today = today or date.today()
    bench_index = benchmarks_by_name(benchmarks)
    signals = _build_signals(stock_df, sales_df, bench_index)

    recs: list[PurchaseRecommendation] = []
    for s in signals:
        if s.bench is None:
            continue
        rec = _recommendation_for(s, s.bench, today)
        if rec is not None:
            recs.append(rec)

    recs.sort(key=lambda r: (r.next_date, -r.urgency, r.product))

    if not recs:
        return pd.DataFrame(
            columns=[
                "Product", "Buy", "Unit cost (R)", "Est. cost (R)", "Supplier",
                "Channel", "Best day", "Next date", "Reason", "Urgency",
            ]
        )
    return pd.DataFrame([r.as_row() for r in recs])


# ---------------------------------------------------------------------------
# Scheduling layer — let the owner accept, override, or skip each line
# ---------------------------------------------------------------------------


SCHEDULE_MODES = ("Auto", "Manual", "Skip")


def add_schedule_columns(
    plan_df: pd.DataFrame,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Add ``Mode`` and ``Scheduled date`` columns to a purchase plan.

    ``overrides`` is a per-product dict like ``{"White bread loaf": {"mode":
    "Manual", "date_iso": "2026-05-22"}}``. Three modes are recognised:

    * **Auto** (default) — the line is included and the scheduled date is
      the supplier's next best-day occurrence (already in ``Next date``).
    * **Manual** — the line is included and the scheduled date is the
      one the owner picked (``date_iso`` field of the override).
    * **Skip** — the line is kept in the table for visibility but ignored
      by ``trip_summary`` and the cost totals.

    Returns a new DataFrame. The input is never mutated.
    """
    overrides = overrides or {}
    new_columns = list(plan_df.columns) + ["Mode", "Scheduled date"]
    if plan_df.empty:
        return pd.DataFrame(columns=new_columns)

    out = plan_df.copy()
    modes: list[str] = []
    dates: list[str] = []
    for _, row in out.iterrows():
        ov = overrides.get(row["Product"], {}) if isinstance(overrides.get(row["Product"], {}), dict) else {}
        raw_mode = ov.get("mode") if isinstance(ov, dict) else None
        mode = raw_mode if raw_mode in SCHEDULE_MODES else "Auto"

        if mode == "Manual":
            override_date = ov.get("date_iso") if isinstance(ov, dict) else None
            scheduled = override_date or row["Next date"]
        else:
            scheduled = row["Next date"]

        modes.append(mode)
        dates.append(scheduled)
    out["Mode"] = modes
    out["Scheduled date"] = dates
    return out


_TRIP_COLUMNS = [
    "Scheduled date", "Best day", "Supplier", "Items",
    "Stock cost (R)", "Transport (R)", "Total (R)",
]


def trip_summary(
    plan_df: pd.DataFrame,
    suppliers: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Group the plan by (scheduled date, supplier) and add transport cost.

    If the plan has been through ``add_schedule_columns``, this honours
    the ``Mode`` (excluding ``Skip`` rows) and ``Scheduled date`` columns.
    Otherwise it falls back to ``Next date`` and includes every row.

    ``suppliers`` is the parsed ``suppliers.json`` dict. If omitted, it's
    loaded from disk so callers (and the UI) can use the function without
    threading the JSON through every call.
    """
    if plan_df.empty:
        return pd.DataFrame(columns=_TRIP_COLUMNS)

    plan = plan_df.copy()
    if "Mode" in plan.columns:
        plan = plan[plan["Mode"] != "Skip"]
    if plan.empty:
        return pd.DataFrame(columns=_TRIP_COLUMNS)

    date_col = "Scheduled date" if "Scheduled date" in plan.columns else "Next date"
    # Normalise dates to ISO strings so groupby is well-defined regardless
    # of whether callers pass strings or pd.Timestamps from the UI editor.
    plan[date_col] = plan[date_col].map(_normalise_date_to_iso)

    if suppliers is None:
        suppliers = load_suppliers()
    transport_lookup = {
        s["name"].lower(): float(s.get("transport_cost_rand", 0) or 0)
        for s in suppliers.get("suppliers", [])
    }

    grouped = (
        plan.groupby([date_col, "Best day", "Supplier"], as_index=False)
        .agg(
            **{
                "Items": ("Product", lambda s: ", ".join(s)),
                "Stock cost (R)": ("Est. cost (R)", "sum"),
            }
        )
        .sort_values([date_col, "Supplier"])
        .reset_index(drop=True)
    )
    grouped["Stock cost (R)"] = grouped["Stock cost (R)"].round(2)
    grouped["Transport (R)"] = grouped["Supplier"].str.lower().map(transport_lookup).fillna(0.0)
    grouped["Total (R)"] = (grouped["Stock cost (R)"] + grouped["Transport (R)"]).round(2)
    grouped = grouped.rename(columns={date_col: "Scheduled date"})
    return grouped[_TRIP_COLUMNS]


def _normalise_date_to_iso(value: Any) -> str:
    """Accept ISO string, ``date``, or ``pd.Timestamp`` and return ISO string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return str(value)


def grand_totals(plan_with_schedule: pd.DataFrame, suppliers: dict[str, Any] | None = None) -> dict[str, float]:
    """Headline totals for the whole plan: stock outlay, transport, grand total.

    Honours scheduling (``Skip`` rows excluded). Transport is summed across
    distinct trips (one per supplier × scheduled date), matching what the
    owner actually pays.
    """
    trips = trip_summary(plan_with_schedule, suppliers=suppliers)
    if trips.empty:
        return {"stock": 0.0, "transport": 0.0, "total": 0.0}
    return {
        "stock": round(float(trips["Stock cost (R)"].sum()), 2),
        "transport": round(float(trips["Transport (R)"].sum()), 2),
        "total": round(float(trips["Total (R)"].sum()), 2),
    }


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------


def schedule_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
