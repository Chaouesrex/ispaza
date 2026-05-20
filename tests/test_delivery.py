"""Unit tests for delivery.py — weekly schedule + purchase plan."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from core import DAYS_OF_WEEK, default_sales, default_stock, load_benchmarks
from delivery import (
    SCHEDULE_MODES,
    PurchaseRecommendation,
    _next_occurrence,
    add_schedule_columns,
    grand_totals,
    purchase_plan,
    schedule_to_csv,
    trip_summary,
    upcoming_deliveries,
    weekly_schedule,
)


@pytest.fixture
def benchmarks() -> dict:
    return load_benchmarks()


# ---------------------------------------------------------------------------
# weekly_schedule
# ---------------------------------------------------------------------------


def test_weekly_schedule_has_seven_rows_in_order(benchmarks):
    df = weekly_schedule(benchmarks)
    assert list(df["Day"]) == list(DAYS_OF_WEEK)


def test_weekly_schedule_columns(benchmarks):
    df = weekly_schedule(benchmarks)
    assert list(df.columns) == ["Day", "Deliveries arriving", "Best to order / buy"]


def test_coca_cola_shows_up_on_tuesday_and_thursday(benchmarks):
    df = weekly_schedule(benchmarks)
    by_day = {row["Day"]: row for _, row in df.iterrows()}
    assert "Coca-Cola 500ml" in by_day["Tuesday"]["Deliveries arriving"]
    assert "Coca-Cola 500ml" in by_day["Thursday"]["Deliveries arriving"]


def test_bread_shows_up_six_days_a_week(benchmarks):
    df = weekly_schedule(benchmarks)
    by_day = {row["Day"]: row for _, row in df.iterrows()}
    for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"):
        assert "White bread loaf" in by_day[day]["Deliveries arriving"], day
    assert "White bread loaf" not in by_day["Sunday"]["Deliveries arriving"]


def test_sunday_is_a_quiet_day(benchmarks):
    df = weekly_schedule(benchmarks)
    sun = df[df["Day"] == "Sunday"].iloc[0]
    assert sun["Deliveries arriving"] == "—"


def test_weekly_schedule_filters_by_products_in_shop(benchmarks):
    df_all = weekly_schedule(benchmarks)
    df_one = weekly_schedule(benchmarks, products_in_shop=["Niknaks 30g"])
    by_day_one = {row["Day"]: row for _, row in df_one.iterrows()}
    # Niknaks delivers on Wednesday — every other day should be a dash for arrivals.
    for day in DAYS_OF_WEEK:
        if day == "Wednesday":
            assert "Niknaks 30g" in by_day_one[day]["Deliveries arriving"]
        else:
            assert by_day_one[day]["Deliveries arriving"] == "—"


def test_best_to_order_column_uses_best_purchase_day(benchmarks):
    df = weekly_schedule(benchmarks)
    by_day = {row["Day"]: row for _, row in df.iterrows()}
    # Coca-Cola's best_purchase_day is Tuesday per the JSON
    assert "Coca-Cola 500ml" in by_day["Tuesday"]["Best to order / buy"]


# ---------------------------------------------------------------------------
# upcoming_deliveries
# ---------------------------------------------------------------------------


def test_upcoming_deliveries_returns_seven_consecutive_days(benchmarks):
    today = date(2026, 5, 20)  # Wednesday
    df = upcoming_deliveries(today, benchmarks)
    assert len(df) == 7
    assert df.iloc[0]["Date"] == "2026-05-20"
    assert df.iloc[6]["Date"] == "2026-05-26"
    assert "today" in df.iloc[0]["Day"]


def test_upcoming_deliveries_aligns_day_names_to_weekday(benchmarks):
    today = date(2026, 5, 20)  # Wednesday
    df = upcoming_deliveries(today, benchmarks)
    # First row should be Wednesday
    assert df.iloc[0]["Day"].startswith("Wednesday")
    assert df.iloc[1]["Day"] == "Thursday"


# ---------------------------------------------------------------------------
# _next_occurrence
# ---------------------------------------------------------------------------


def test_next_occurrence_returns_today_when_matching():
    # 2026-05-20 is a Wednesday
    assert _next_occurrence(date(2026, 5, 20), "Wednesday") == date(2026, 5, 20)


def test_next_occurrence_wraps_to_next_week():
    # Wednesday → next Tuesday is 6 days later
    assert _next_occurrence(date(2026, 5, 20), "Tuesday") == date(2026, 5, 26)


def test_next_occurrence_unknown_day_returns_today():
    assert _next_occurrence(date(2026, 5, 20), "Yesterday") == date(2026, 5, 20)


# ---------------------------------------------------------------------------
# purchase_plan
# ---------------------------------------------------------------------------


def test_purchase_plan_default_demo_recommends_bread(benchmarks):
    """Default demo has White bread sold out → bread must appear at the top."""
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    assert not plan.empty
    assert "White bread loaf" in plan["Product"].tolist()


def test_purchase_plan_assigns_correct_supplier_and_channel(benchmarks):
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    bread = plan[plan["Product"] == "White bread loaf"].iloc[0]
    assert "Sasko" in bread["Supplier"]
    assert bread["Channel"] == "direct delivery"

    coke_stock = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Quantity": 2}])
    coke_sales = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Units Sold": 30}])
    coke_plan = purchase_plan(coke_stock, coke_sales, benchmarks, today=today)
    assert "Coca-Cola SA depot" in coke_plan.iloc[0]["Supplier"]


def test_purchase_plan_rounds_quantity_to_pack_size(benchmarks):
    """Coca-Cola has wholesale_pack_size = 24. Recommended quantity must be a multiple of 24."""
    today = date(2026, 5, 20)
    stock = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Quantity": 2}])
    sales = pd.DataFrame([{"Product": "Coca-Cola 500ml", "Units Sold": 30}])
    plan = purchase_plan(stock, sales, benchmarks, today=today)
    qty_text = plan.iloc[0]["Buy"]
    qty = int(qty_text.split()[0])
    assert qty % 24 == 0, f"{qty} is not a full case multiple"


def test_purchase_plan_marks_cash_and_carry_channel(benchmarks):
    today = date(2026, 5, 20)
    stock = pd.DataFrame([{"Product": "Maggi 2-min noodles", "Quantity": 0}])
    sales = pd.DataFrame([{"Product": "Maggi 2-min noodles", "Units Sold": 50}])
    plan = purchase_plan(stock, sales, benchmarks, today=today)
    row = plan.iloc[0]
    assert "Jumbo" in row["Supplier"]
    assert row["Channel"] == "cash and carry"


def test_purchase_plan_skips_products_without_signal(benchmarks):
    """A product with plenty of stock and steady sales should not appear."""
    today = date(2026, 5, 20)
    stock = pd.DataFrame([{"Product": "Niknaks 30g", "Quantity": 200}])
    sales = pd.DataFrame([{"Product": "Niknaks 30g", "Units Sold": 5}])
    plan = purchase_plan(stock, sales, benchmarks, today=today)
    assert "Niknaks 30g" not in plan["Product"].tolist()


def test_purchase_plan_empty_when_no_action_needed(benchmarks):
    today = date(2026, 5, 20)
    plan = purchase_plan(
        pd.DataFrame(columns=["Product", "Quantity"]),
        pd.DataFrame(columns=["Product", "Units Sold"]),
        benchmarks,
        today=today,
    )
    assert plan.empty
    assert "Product" in plan.columns
    assert "Reason" in plan.columns
    assert "Unit cost (R)" in plan.columns


def test_purchase_plan_sorts_earliest_date_first(benchmarks):
    """Plan rows should be ordered by the date the owner needs to act on."""
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    dates = plan["Next date"].tolist()
    assert dates == sorted(dates)


def test_purchase_plan_includes_unit_and_total_cost(benchmarks):
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    assert (plan["Est. cost (R)"] > 0).all()
    assert (plan["Unit cost (R)"] > 0).all()


def test_purchase_plan_renames_why_column_to_reason(benchmarks):
    """The user asked for 'Reason' wording — make sure 'Why' is gone."""
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    assert "Reason" in plan.columns
    assert "Why" not in plan.columns


# ---------------------------------------------------------------------------
# trip_summary
# ---------------------------------------------------------------------------


def test_trip_summary_groups_items_by_supplier_and_day(benchmarks):
    today = date(2026, 5, 20)
    plan = purchase_plan(default_stock(), default_sales(), benchmarks, today=today)
    trips = trip_summary(plan)
    # One Sasko trip on White-bread day, one Jumbo trip if any cash-and-carry items, etc.
    assert "Supplier" in trips.columns
    assert "Items" in trips.columns
    # Every Items cell should be a non-empty comma-joined string
    assert (trips["Items"].str.len() > 0).all()


def _three_line_plan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Product": "A", "Buy": "10 units", "Unit cost (R)": 5.0,
                "Est. cost (R)": 100.0, "Supplier": "Coca-Cola SA depot",
                "Channel": "direct delivery", "Best day": "Tuesday",
                "Next date": "2026-05-26", "Reason": "...", "Urgency": 50,
            },
            {
                "Product": "B", "Buy": "5 units", "Unit cost (R)": 15.0,
                "Est. cost (R)": 75.0, "Supplier": "Coca-Cola SA depot",
                "Channel": "direct delivery", "Best day": "Tuesday",
                "Next date": "2026-05-26", "Reason": "...", "Urgency": 60,
            },
            {
                "Product": "C", "Buy": "6 units", "Unit cost (R)": 50.0,
                "Est. cost (R)": 300.0, "Supplier": "Jumbo Cash & Carry",
                "Channel": "cash and carry", "Best day": "Tuesday",
                "Next date": "2026-05-26", "Reason": "...", "Urgency": 40,
            },
        ]
    )


def test_trip_summary_sums_costs_and_adds_transport():
    """Direct-delivery suppliers have R0 transport; cash-and-carry adds Jumbo's R80."""
    df = _three_line_plan()
    trips = trip_summary(df)
    # Two trips: Coca-Cola depot (R0 transport, R175 stock) and Jumbo (R80 transport, R300 stock).
    cc = trips[trips["Supplier"] == "Coca-Cola SA depot"].iloc[0]
    assert cc["Stock cost (R)"] == 175.0
    assert cc["Transport (R)"] == 0.0
    assert cc["Total (R)"] == 175.0

    jumbo = trips[trips["Supplier"] == "Jumbo Cash & Carry"].iloc[0]
    assert jumbo["Stock cost (R)"] == 300.0
    assert jumbo["Transport (R)"] == 80.0
    assert jumbo["Total (R)"] == 380.0


def test_trip_summary_empty_input_returns_empty_df():
    empty = pd.DataFrame(
        columns=[
            "Product", "Buy", "Unit cost (R)", "Est. cost (R)", "Supplier",
            "Channel", "Best day", "Next date", "Reason", "Urgency",
        ]
    )
    trips = trip_summary(empty)
    assert trips.empty
    assert "Supplier" in trips.columns
    assert "Transport (R)" in trips.columns
    assert "Total (R)" in trips.columns
    assert "Scheduled date" in trips.columns


# ---------------------------------------------------------------------------
# Scheduling layer
# ---------------------------------------------------------------------------


def test_add_schedule_columns_defaults_to_auto_with_supplier_day():
    """No overrides → every row is Auto, scheduled on the supplier's best day."""
    df = _three_line_plan()
    sched = add_schedule_columns(df)
    assert (sched["Mode"] == "Auto").all()
    assert (sched["Scheduled date"] == sched["Next date"]).all()


def test_add_schedule_columns_honours_manual_override():
    df = _three_line_plan()
    overrides = {"A": {"mode": "Manual", "date_iso": "2026-05-28"}}
    sched = add_schedule_columns(df, overrides=overrides)
    row_a = sched[sched["Product"] == "A"].iloc[0]
    assert row_a["Mode"] == "Manual"
    assert row_a["Scheduled date"] == "2026-05-28"
    # Other rows untouched
    row_b = sched[sched["Product"] == "B"].iloc[0]
    assert row_b["Mode"] == "Auto"
    assert row_b["Scheduled date"] == row_b["Next date"]


def test_add_schedule_columns_honours_skip_override():
    df = _three_line_plan()
    sched = add_schedule_columns(df, overrides={"C": {"mode": "Skip"}})
    row_c = sched[sched["Product"] == "C"].iloc[0]
    assert row_c["Mode"] == "Skip"


def test_add_schedule_columns_unknown_mode_falls_back_to_auto():
    df = _three_line_plan()
    sched = add_schedule_columns(df, overrides={"A": {"mode": "Garbage"}})
    assert sched[sched["Product"] == "A"].iloc[0]["Mode"] == "Auto"


def test_add_schedule_columns_empty_plan_returns_empty_with_new_columns():
    empty = pd.DataFrame(columns=["Product", "Next date"])
    sched = add_schedule_columns(empty)
    assert sched.empty
    assert "Mode" in sched.columns
    assert "Scheduled date" in sched.columns


def test_schedule_modes_constant_lists_three_options():
    assert set(SCHEDULE_MODES) == {"Auto", "Manual", "Skip"}


def test_trip_summary_excludes_skipped_rows():
    df = _three_line_plan()
    sched = add_schedule_columns(df, overrides={"C": {"mode": "Skip"}})
    trips = trip_summary(sched)
    # Jumbo's trip (C) is skipped — only the Coca-Cola trip remains.
    suppliers_in_trips = trips["Supplier"].tolist()
    assert "Jumbo Cash & Carry" not in suppliers_in_trips
    assert "Coca-Cola SA depot" in suppliers_in_trips


def test_trip_summary_uses_scheduled_date_when_manual_overrides_move_it():
    """A manual date shouldn't be silently snapped back to the supplier's best day."""
    df = _three_line_plan()
    sched = add_schedule_columns(
        df, overrides={"A": {"mode": "Manual", "date_iso": "2026-05-30"}}
    )
    trips = trip_summary(sched)
    # Now there should be TWO Coca-Cola trips (one on the manual 5/30, one on the default 5/26).
    cc_trips = trips[trips["Supplier"] == "Coca-Cola SA depot"]
    assert len(cc_trips) == 2
    dates = set(cc_trips["Scheduled date"])
    assert dates == {"2026-05-26", "2026-05-30"}


def test_trip_summary_all_skipped_returns_empty():
    df = _three_line_plan()
    sched = add_schedule_columns(
        df,
        overrides={
            "A": {"mode": "Skip"},
            "B": {"mode": "Skip"},
            "C": {"mode": "Skip"},
        },
    )
    trips = trip_summary(sched)
    assert trips.empty


# ---------------------------------------------------------------------------
# grand_totals
# ---------------------------------------------------------------------------


def test_grand_totals_sums_stock_plus_transport():
    df = _three_line_plan()
    sched = add_schedule_columns(df)
    totals = grand_totals(sched)
    # Stock = 175 + 300 = 475; transport = 0 + 80 = 80; total = 555
    assert totals == {"stock": 475.0, "transport": 80.0, "total": 555.0}


def test_grand_totals_drops_skipped_rows_from_all_columns():
    df = _three_line_plan()
    sched = add_schedule_columns(df, overrides={"C": {"mode": "Skip"}})
    totals = grand_totals(sched)
    # Jumbo trip gone → no transport, no Jumbo stock cost.
    assert totals["transport"] == 0.0
    assert totals["stock"] == 175.0
    assert totals["total"] == 175.0


def test_grand_totals_empty_plan_returns_zeroes():
    empty = pd.DataFrame(columns=["Product", "Next date"])
    assert grand_totals(empty) == {"stock": 0.0, "transport": 0.0, "total": 0.0}


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_schedule_csv_roundtrip(benchmarks):
    df = weekly_schedule(benchmarks)
    csv = schedule_to_csv(df).decode("utf-8")
    assert "Monday" in csv and "Sunday" in csv
    assert csv.splitlines()[0].startswith("Day,")
