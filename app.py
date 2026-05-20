"""iSpaza — AI Advisor for Spaza Shop Owners.

Streamlit app for the IEB TechWays AI Hackathon 2026.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from advisor import generate_advice_markdown
from catalog import (
    add_to_stock,
    catalog_df,
    filter_catalog,
    list_categories,
)
from core import (
    Advice,
    default_sales,
    default_stock,
    load_benchmarks,
    load_suppliers,
    parse_advice_response,
)
from delivery import (
    SCHEDULE_MODES,
    add_schedule_columns,
    grand_totals,
    purchase_plan,
    schedule_to_csv,
    trip_summary,
    upcoming_deliveries,
    weekly_schedule,
)
from quick_actions import quick_actions_df, quick_actions_to_csv
from tracker import (
    Sale,
    daily_profit_breakdown,
    default_purchase_log,
    default_sales_log,
    product_profit_breakdown,
    purchases_to_df,
    running_totals,
    sales_to_df,
    total_cost_of_goods,
    total_profit,
    total_revenue,
    units_by_product,
    units_pivot_by_day,
)


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="iSpaza",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIMARY_GREEN = "#006B3C"
ACCENT_YELLOW = "#FFB81C"
SOFT_BG = "#F4F6F2"

st.markdown(
    f"""
    <style>
      .ispaza-header {{
        padding: 1.1rem 1.3rem;
        border-radius: 14px;
        background: linear-gradient(95deg, {PRIMARY_GREEN} 0%, #00854b 100%);
        color: white;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 14px rgba(0, 107, 60, 0.18);
      }}
      .ispaza-header h1 {{
        margin: 0;
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.01em;
      }}
      .ispaza-header .tagline {{
        margin-top: 0.2rem;
        font-size: 1rem;
        opacity: 0.92;
        font-weight: 400;
      }}
      .ispaza-header .tagline .accent {{
        color: {ACCENT_YELLOW};
        font-weight: 600;
      }}
      .stButton > button[kind="primary"] {{
        background-color: {PRIMARY_GREEN};
        border-color: {PRIMARY_GREEN};
        font-weight: 600;
        padding: 0.55rem 1.1rem;
      }}
      .stButton > button[kind="primary"]:hover {{
        background-color: #00854b;
        border-color: #00854b;
      }}
      .info-banner {{
        background: {SOFT_BG};
        border-left: 5px solid {PRIMARY_GREEN};
        padding: 0.85rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-size: 0.95rem;
      }}
      .info-banner.accent {{
        border-left-color: {ACCENT_YELLOW};
      }}
      .confidence-line {{
        margin-top: 0.6rem;
        color: #555;
        font-size: 0.92rem;
      }}
      .footer {{
        margin-top: 2.5rem;
        padding-top: 0.8rem;
        border-top: 1px solid #eee;
        color: #888;
        font-size: 0.85rem;
        text-align: center;
      }}
      .section-divider {{
        height: 1px;
        background: #eee;
        margin: 1.6rem 0 1.2rem 0;
      }}
      .catalog-card {{
        padding: 0.6rem 0.2rem;
      }}
      .catalog-card .price {{
        font-size: 1.05rem;
        font-weight: 700;
        color: {PRIMARY_GREEN};
      }}
      .catalog-card .margin {{
        color: #555;
        font-size: 0.85rem;
      }}
      .catalog-card .meta {{
        color: #666;
        font-size: 0.85rem;
        margin-top: 0.2rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="ispaza-header">
      <h1>iSpaza</h1>
      <div class="tagline">
        <span class="accent">Better decisions today.</span> Banking tomorrow.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Cached loaders
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def cached_benchmarks() -> dict:
    return load_benchmarks()


@st.cache_data(show_spinner=False)
def cached_suppliers() -> dict:
    return load_suppliers()


@st.cache_data(show_spinner=False)
def cached_catalog_df() -> pd.DataFrame:
    return catalog_df(load_benchmarks())


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

_today = date.today()
_benchmarks = cached_benchmarks()

if "latest_advice" not in st.session_state:
    st.session_state.latest_advice = None

if "latest_quick_df" not in st.session_state:
    st.session_state.latest_quick_df = None

if "stock_df" not in st.session_state:
    st.session_state.stock_df = default_stock()

if "sales_df" not in st.session_state:
    st.session_state.sales_df = default_sales()

if "purchase_log_df" not in st.session_state:
    st.session_state.purchase_log_df = purchases_to_df(
        default_purchase_log(today=_today, benchmarks=_benchmarks)
    )

if "sales_log_df" not in st.session_state:
    st.session_state.sales_log_df = sales_to_df(
        default_sales_log(today=_today, benchmarks=_benchmarks)
    )

if "advice_mode" not in st.session_state:
    st.session_state.advice_mode = "Worded advice"

if "browse_query" not in st.session_state:
    st.session_state.browse_query = ""

if "browse_categories" not in st.session_state:
    st.session_state.browse_categories = []

if "schedule_overrides" not in st.session_state:
    st.session_state.schedule_overrides = {}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"### 🏪 Shop details")
    shop_name = st.text_input("Shop name", value="Mama Thandi's Spaza")
    location = st.text_input("Location", value="Diepkloof, Soweto")

    st.divider()

    with st.expander("ℹ️ About iSpaza"):
        st.markdown(
            """
**iSpaza helps you:**

1. **Decide** what to restock, what to reprice, and what new product to try.
2. **Plan** which day to be at which supplier (Sasko, Coca-Cola depot,
   the Simba rep, Jumbo Cash & Carry).
3. **Track** daily profit per product so you know exactly which lines
   pay the rent.
4. **Browse** the catalogue and add new products to your stock with
   one click.
            """
        )

    st.divider()
    st.caption("Built for the IEB TechWays AI Hackathon 2026.")


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_worded_advice(advice: Advice) -> None:
    cards = [
        ("🔄 Restock this week", advice.restock),
        ("💰 Pricing adjustments", advice.pricing),
        ("➕ One product to add", advice.add),
    ]
    for title, body in cards:
        with st.container(border=True):
            st.markdown(f"#### {title}")
            if body:
                st.markdown(body)
            else:
                st.caption("_No content returned for this section._")

    st.markdown(
        f"<div class='confidence-line'><em>Confidence: "
        f"<strong>{advice.confidence}</strong></em></div>",
        unsafe_allow_html=True,
    )


def render_quick_actions(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No actions — add stock and sales data and click _Get advice_.")
        return

    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        column_config={
            "Action": st.column_config.TextColumn("Action", width="small"),
            "Product": st.column_config.TextColumn("Product", width="medium"),
            "Adjust": st.column_config.TextColumn("Adjust", width="small"),
            "By": st.column_config.TextColumn("By", width="small"),
            "Reason": st.column_config.TextColumn("Reason", width="large"),
            "Priority": st.column_config.ProgressColumn(
                "Priority",
                min_value=0,
                max_value=100,
                format="%d",
                width="small",
            ),
        },
    )
    st.download_button(
        "⬇️ Download these actions (CSV)",
        data=quick_actions_to_csv(df),
        file_name=f"ispaza_quick_actions_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_advice, tab_profit, tab_delivery, tab_browse = st.tabs(
    [
        "💡 Get Advice",
        "💰 Profit Tracker",
        "🚚 Delivery & Purchasing",
        "🛍️ Browse Products",
    ]
)


# ----- Tab 1: Get Advice ---------------------------------------------------


with tab_advice:
    st.subheader("Tell iSpaza what's on your shelves and what sold last week")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("**📦 Current Stock**")
        st.caption("What's on your shelves right now.")
        st.session_state.stock_df = st.data_editor(
            st.session_state.stock_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn(
                    "Product", required=True, width="medium"
                ),
                "Quantity": st.column_config.NumberColumn(
                    "Quantity", min_value=0, step=1, format="%d"
                ),
            },
            key="stock_editor",
        )

    with right:
        st.markdown("**🧾 Last Week's Sales**")
        st.caption("How many of each you sold in the past 7 days.")
        st.session_state.sales_df = st.data_editor(
            st.session_state.sales_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn(
                    "Product", required=True, width="medium"
                ),
                "Units Sold": st.column_config.NumberColumn(
                    "Units Sold", min_value=0, step=1, format="%d"
                ),
            },
            key="sales_editor",
        )

    st.write("")

    mode_col, btn_col = st.columns([2, 1])
    with mode_col:
        st.session_state.advice_mode = st.radio(
            "Advice style",
            ["Worded advice", "Quick actions"],
            horizontal=True,
            help=(
                "**Worded** — three short sections you can read like a brief. "
                "**Quick actions** — a table of one-line bumps (⬆️ Increase / "
                "⬇️ Decrease / ⏸️ Hold), the specific amount, and a reason."
            ),
            key="advice_mode_radio",
        )
    with btn_col:
        st.write("")
        clicked = st.button("Get advice from iSpaza", type="primary", width="stretch")

    if clicked:
        try:
            benchmarks = cached_benchmarks()
            with st.spinner("iSpaza is thinking…"):
                raw_text = generate_advice_markdown(
                    shop_name,
                    location,
                    st.session_state.stock_df,
                    st.session_state.sales_df,
                    benchmarks,
                )
                quick_df = quick_actions_df(
                    st.session_state.stock_df,
                    st.session_state.sales_df,
                    benchmarks,
                )
            advice = parse_advice_response(raw_text)
            st.session_state.latest_advice = advice
            st.session_state.latest_quick_df = quick_df
        except Exception as e:  # noqa: BLE001 - surface in UI for the demo
            st.error(f"Something went wrong: {e}")

    has_worded = st.session_state.latest_advice is not None
    has_quick = st.session_state.latest_quick_df is not None
    if has_worded or has_quick:
        st.write("")
        st.markdown("### iSpaza's advice")
        if st.session_state.advice_mode == "Worded advice" and has_worded:
            render_worded_advice(st.session_state.latest_advice)
        elif st.session_state.advice_mode == "Quick actions" and has_quick:
            render_quick_actions(st.session_state.latest_quick_df)


# ----- Tab 2: Profit Tracker ----------------------------------------------


with tab_profit:
    st.subheader("Profit Tracker — what your shop is actually earning")

    sales_records = [
        Sale(
            date=date.fromisoformat(str(row["Date"])),
            product=str(row["Product"]),
            quantity=int(row["Units"]),
            unit_price_rand=float(row["Unit Price (R)"]),
            unit_cost_rand=float(row["Unit Cost (R)"]),
        )
        for _, row in st.session_state.sales_log_df.iterrows()
        if str(row.get("Product", "")).strip()
        and not pd.isna(row.get("Units"))
        and int(row["Units"]) > 0
    ]

    rev = total_revenue(sales_records)
    cog = total_cost_of_goods(sales_records)
    profit = total_profit(sales_records)
    margin = (profit / rev * 100) if rev else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Revenue (R)", f"R{rev:,.2f}")
    k2.metric("Cost of goods (R)", f"R{cog:,.2f}")
    k3.metric("Profit (R)", f"R{profit:,.2f}")
    k4.metric("Margin", f"{margin:.1f}%")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    chart_col, breakdown_col = st.columns([3, 2], gap="large")

    with chart_col:
        st.markdown("#### Daily profit")
        running = running_totals(sales_records)
        if running.empty:
            st.info("Add some sales below to see your profit line.")
        else:
            chart_df = running.set_index("Date")[["Profit (R)", "Cumulative Profit (R)"]]
            st.line_chart(chart_df, height=320, color=[PRIMARY_GREEN, ACCENT_YELLOW])
            st.caption("Green = profit per day · Yellow = cumulative.")

    with breakdown_col:
        st.markdown("#### Per-product breakdown")
        per_product = product_profit_breakdown(sales_records)
        if per_product.empty:
            st.info("No product breakdown yet.")
        else:
            st.dataframe(
                per_product,
                width="stretch",
                hide_index=True,
                column_config={
                    "Profit (R)": st.column_config.NumberColumn(format="R%.2f"),
                    "Revenue (R)": st.column_config.NumberColumn(format="R%.2f"),
                    "Cost (R)": st.column_config.NumberColumn(format="R%.2f"),
                    "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### Units sold")
    units_col_a, units_col_b = st.columns(2, gap="large")
    with units_col_a:
        st.markdown("**By product** (total over window)")
        by_product = units_by_product(sales_records)
        if by_product.empty:
            st.info("No sales recorded yet.")
        else:
            st.bar_chart(
                by_product.set_index("Product")["Units"],
                height=300,
                color=PRIMARY_GREEN,
            )
    with units_col_b:
        st.markdown("**By day** (stacked by product)")
        pivot = units_pivot_by_day(sales_records)
        if pivot.empty:
            st.info("No sales recorded yet.")
        else:
            st.bar_chart(pivot, stack=True, height=300)
            st.caption("Hover to see each product's contribution per day.")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### Daily breakdown")
    daily = daily_profit_breakdown(sales_records)
    if daily.empty:
        st.info("No daily data yet.")
    else:
        st.dataframe(
            daily,
            width="stretch",
            hide_index=True,
            column_config={
                "Revenue (R)": st.column_config.NumberColumn(format="R%.2f"),
                "Cost (R)": st.column_config.NumberColumn(format="R%.2f"),
                "Profit (R)": st.column_config.NumberColumn(format="R%.2f"),
                "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    log_left, log_right = st.columns(2, gap="large")

    with log_left:
        st.markdown("**🧾 Sales log**")
        st.caption(
            "One row per product per day. Edit unit price/cost to see profit update."
        )
        st.session_state.sales_log_df = st.data_editor(
            st.session_state.sales_log_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", help="YYYY-MM-DD"),
                "Product": st.column_config.TextColumn("Product", required=True),
                "Units": st.column_config.NumberColumn(
                    "Units", min_value=0, step=1, format="%d"
                ),
                "Unit Price (R)": st.column_config.NumberColumn(
                    "Unit Price", min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Unit Cost (R)": st.column_config.NumberColumn(
                    "Unit Cost", min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Revenue (R)": st.column_config.NumberColumn(
                    "Revenue", format="R%.2f", disabled=True
                ),
                "Cost (R)": st.column_config.NumberColumn(
                    "Cost", format="R%.2f", disabled=True
                ),
                "Profit (R)": st.column_config.NumberColumn(
                    "Profit", format="R%.2f", disabled=True
                ),
            },
            key="sales_log_editor",
        )
        st.download_button(
            "⬇️ Sales log (CSV)",
            data=st.session_state.sales_log_df.to_csv(index=False).encode("utf-8"),
            file_name=f"ispaza_sales_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

    with log_right:
        st.markdown("**📥 Purchase log**")
        st.caption("Every stock-in event — track what you paid and to whom.")
        st.session_state.purchase_log_df = st.data_editor(
            st.session_state.purchase_log_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn("Date", help="YYYY-MM-DD"),
                "Product": st.column_config.TextColumn("Product", required=True),
                "Quantity": st.column_config.NumberColumn(
                    "Quantity", min_value=0, step=1, format="%d"
                ),
                "Unit Cost (R)": st.column_config.NumberColumn(
                    "Unit Cost", min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Total Cost (R)": st.column_config.NumberColumn(
                    "Total Cost", format="R%.2f", disabled=True
                ),
                "Supplier": st.column_config.TextColumn("Supplier"),
            },
            key="purchase_log_editor",
        )
        st.download_button(
            "⬇️ Purchase log (CSV)",
            data=st.session_state.purchase_log_df.to_csv(index=False).encode("utf-8"),
            file_name=f"ispaza_purchases_{date.today().isoformat()}.csv",
            mime="text/csv",
        )


# ----- Tab 3: Delivery & Purchasing ----------------------------------------


with tab_delivery:
    st.subheader("Delivery & Purchasing — what to buy, where, and when")

    benchmarks = cached_benchmarks()
    suppliers = cached_suppliers()
    today = date.today()

    stocked_products = list(st.session_state.stock_df.get("Product", []))

    st.markdown(
        f"""
        <div class="info-banner accent">
          📅 <strong>This week's plan</strong> below combines your live stock /
          sales numbers with realistic supplier patterns for Gauteng townships.
          Each line auto-schedules to the supplier's best day — switch to
          <em>Manual</em> to pick your own date or <em>Skip</em> to drop it.
          The grand total includes stock outlay <strong>plus</strong>
          transport (R0 for direct delivery, ~R80 per Jumbo Cash &amp; Carry trip).
        </div>
        """,
        unsafe_allow_html=True,
    )

    base_plan = purchase_plan(
        st.session_state.stock_df,
        st.session_state.sales_df,
        benchmarks,
        today=today,
    )
    plan = add_schedule_columns(base_plan, overrides=st.session_state.schedule_overrides)

    st.markdown("#### This week's purchase plan")
    if plan.empty:
        st.success(
            "✅ Nothing urgent to source this week — stock levels are matching demand."
        )
        # Reset overrides for products no longer in the plan
        st.session_state.schedule_overrides = {}
    else:
        # Convert Scheduled date column to pd.Timestamp so DateColumn renders it
        plan_for_editor = plan.copy()
        plan_for_editor["Scheduled date"] = pd.to_datetime(
            plan_for_editor["Scheduled date"]
        )

        edited_plan = st.data_editor(
            plan_for_editor,
            width="stretch",
            hide_index=True,
            key="purchase_plan_editor",
            disabled=[
                "Product", "Buy", "Unit cost (R)", "Est. cost (R)",
                "Supplier", "Channel", "Best day", "Next date",
                "Reason", "Urgency",
            ],
            column_config={
                "Buy": st.column_config.TextColumn("Buy", width="small"),
                "Unit cost (R)": st.column_config.NumberColumn(
                    "Unit cost", format="R%.2f"
                ),
                "Est. cost (R)": st.column_config.NumberColumn(
                    "Line cost", format="R%.2f"
                ),
                "Supplier": st.column_config.TextColumn("Supplier", width="medium"),
                "Channel": st.column_config.TextColumn("Channel", width="small"),
                "Best day": st.column_config.TextColumn("Best day", width="small"),
                "Next date": st.column_config.TextColumn(
                    "Auto date", width="small", help="Supplier's next best day."
                ),
                "Mode": st.column_config.SelectboxColumn(
                    "Schedule",
                    options=list(SCHEDULE_MODES),
                    required=True,
                    width="small",
                    help=(
                        "Auto = use the supplier's best day · "
                        "Manual = pick your own date · "
                        "Skip = drop from totals"
                    ),
                ),
                "Scheduled date": st.column_config.DateColumn(
                    "Scheduled date",
                    width="small",
                    format="YYYY-MM-DD",
                    help="When you're actually going to buy this. Manual edits switch the schedule to Manual.",
                ),
                "Reason": st.column_config.TextColumn("Reason", width="large"),
                "Urgency": st.column_config.ProgressColumn(
                    "Urgency", min_value=0, max_value=100, format="%d", width="small"
                ),
            },
            column_order=[
                "Product", "Buy", "Unit cost (R)", "Est. cost (R)",
                "Supplier", "Mode", "Scheduled date", "Best day",
                "Next date", "Reason", "Urgency",
            ],
        )

        # Persist user changes back to session state.
        new_overrides: dict[str, dict[str, object]] = {}
        for _, row in edited_plan.iterrows():
            name = str(row["Product"])
            mode = str(row["Mode"])
            scheduled_val = row["Scheduled date"]
            auto_iso = str(row["Next date"])
            try:
                scheduled_iso = pd.Timestamp(scheduled_val).date().isoformat()
            except (TypeError, ValueError):
                scheduled_iso = auto_iso

            if mode == "Skip":
                new_overrides[name] = {"mode": "Skip", "date_iso": None}
            elif mode == "Manual" or scheduled_iso != auto_iso:
                # If the user moved the date but left Mode = Auto, promote to Manual.
                new_overrides[name] = {"mode": "Manual", "date_iso": scheduled_iso}
            # mode == Auto and date unchanged → no override needed.
        st.session_state.schedule_overrides = new_overrides

        # Rebuild the schedule-aware plan with the just-applied overrides so the
        # totals always match what the editor shows on the next render.
        plan_for_totals = add_schedule_columns(base_plan, overrides=new_overrides)
        plan_for_totals["Scheduled date"] = plan_for_totals["Scheduled date"].map(
            lambda v: pd.Timestamp(v).date().isoformat() if pd.notna(v) else v
        )

        totals = grand_totals(plan_for_totals, suppliers=suppliers)
        included_count = int((plan_for_totals["Mode"] != "Skip").sum())
        skipped_count = len(plan_for_totals) - included_count
        skip_note = f" · {skipped_count} skipped" if skipped_count else ""
        st.caption(
            f"{included_count} included{skip_note} · "
            f"stock **R{totals['stock']:,.2f}** + "
            f"transport **R{totals['transport']:,.2f}** = "
            f"**R{totals['total']:,.2f}**"
        )

        st.download_button(
            "⬇️ Purchase plan (CSV)",
            data=schedule_to_csv(plan_for_totals),
            file_name=f"ispaza_purchase_plan_{today.isoformat()}.csv",
            mime="text/csv",
        )

        st.markdown("#### Combined trips (with transport cost)")
        st.caption(
            "Grouped by the day you'll be at each supplier — fewer trips, "
            "less transport cost. Skipped lines are excluded."
        )
        trips = trip_summary(plan_for_totals, suppliers=suppliers)
        if trips.empty:
            st.info("Every line is set to Skip — no trips this week.")
        else:
            st.dataframe(
                trips,
                width="stretch",
                hide_index=True,
                column_config={
                    "Stock cost (R)": st.column_config.NumberColumn(
                        "Stock cost", format="R%.2f"
                    ),
                    "Transport (R)": st.column_config.NumberColumn(
                        "Transport", format="R%.2f"
                    ),
                    "Total (R)": st.column_config.NumberColumn("Total", format="R%.2f"),
                },
            )
            st.markdown(
                f"<div class='info-banner'><strong>Grand total this week:</strong> "
                f"R{totals['total']:,.2f} "
                f"&nbsp;·&nbsp; stock R{totals['stock']:,.2f} "
                f"&nbsp;+&nbsp; transport R{totals['transport']:,.2f}</div>",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### Next 7 days")
    upcoming = upcoming_deliveries(
        today,
        benchmarks,
        products_in_shop=stocked_products if stocked_products else None,
    )
    st.dataframe(upcoming, width="stretch", hide_index=True)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### Reference: typical week (your stock)")
    schedule = weekly_schedule(
        benchmarks,
        products_in_shop=stocked_products if stocked_products else None,
    )
    st.dataframe(schedule, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Weekly schedule (CSV)",
        data=schedule_to_csv(schedule),
        file_name=f"ispaza_weekly_schedule_{today.isoformat()}.csv",
        mime="text/csv",
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### Supplier notes")
    for sup in suppliers.get("suppliers", []):
        with st.container(border=True):
            channel = sup["channel"].replace("_", " ")
            days = ", ".join(sup.get("delivery_days", [])) or "—"
            transport = float(sup.get("transport_cost_rand", 0) or 0)
            min_order = float(sup.get("min_order_rand", 0) or 0)
            transport_str = f"R{transport:.0f}" if transport else "free"
            min_order_str = (
                f"R{min_order:.0f} minimum" if min_order else "no minimum"
            )
            st.markdown(
                f"**{sup['name']}** · _{channel}_  \n"
                f"**Delivers:** {days} · **Best to order:** "
                f"{sup.get('best_order_day', '—')} · "
                f"**Lead time:** {sup.get('lead_time_days', 0)} day"
                f"{'s' if sup.get('lead_time_days', 0) != 1 else ''}  \n"
                f"**Transport:** {transport_str} · {min_order_str}"
            )
            products_line = ", ".join(sup.get("products", []))
            if products_line:
                st.caption(f"Products: {products_line}")
            notes = sup.get("notes")
            if notes:
                st.markdown(f"_{notes}_")


# ----- Tab 4: Browse Products ----------------------------------------------


with tab_browse:
    st.subheader("Browse Products — pick something to add to your stock")

    catalog = cached_catalog_df()
    categories = list_categories(cached_benchmarks())

    st.markdown(
        f"""
        <div class="info-banner accent">
          🛍️ The catalogue covers <strong>{len(catalog)} products</strong>
          across {len(categories)} categories, each with cost price,
          township median price, margin, supplier, and best purchase day.
          Click <em>Add to my stock</em> on any card and the product
          appears on the <em>Get Advice</em> tab.
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_col, cat_col = st.columns([3, 4], gap="large")
    with search_col:
        st.session_state.browse_query = st.text_input(
            "Search products, suppliers, or categories",
            value=st.session_state.browse_query,
            placeholder="e.g. bread, Coca-Cola, snacks",
            key="browse_query_input",
        )
    with cat_col:
        st.session_state.browse_categories = st.multiselect(
            "Filter by category",
            options=categories,
            default=st.session_state.browse_categories,
            key="browse_categories_input",
        )

    filtered = filter_catalog(
        catalog,
        query=st.session_state.browse_query,
        categories=st.session_state.browse_categories,
    )

    st.caption(
        f"Showing **{len(filtered)}** of {len(catalog)} products."
        + (" Clear filters to see everything." if len(filtered) < len(catalog) else "")
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    if filtered.empty:
        st.warning("No products match your filters.")
    else:
        per_row = 3
        rows = (len(filtered) + per_row - 1) // per_row
        for r in range(rows):
            cols = st.columns(per_row, gap="medium")
            for c, col in enumerate(cols):
                idx = r * per_row + c
                if idx >= len(filtered):
                    break
                row = filtered.iloc[idx]
                with col:
                    with st.container(border=True):
                        st.markdown(
                            f"<div class='catalog-card'>"
                            f"<div><strong>{row['Product']}</strong></div>"
                            f"<div class='price'>R{row['Median price (R)']:.2f}"
                            f" <span class='margin'>"
                            f"· cost R{row['Cost (R)']:.2f}"
                            f" · margin {row['Margin %']:.1f}%"
                            f"</span></div>"
                            f"<div class='meta'>"
                            f"{row['Category'].title()} · "
                            f"{row['Range (R)']}"
                            f"</div>"
                            f"<div class='meta'>"
                            f"Supplier: {row['Supplier']}"
                            f"</div>"
                            f"<div class='meta'>"
                            f"Best day: {row['Best day']} · "
                            f"pack of {row['Pack size']}"
                            f"</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        add_col, qty_col = st.columns([3, 2])
                        with qty_col:
                            qty = st.number_input(
                                "Qty",
                                min_value=1,
                                value=int(row["Pack size"]),
                                step=1,
                                key=f"browse_qty_{row['Product']}",
                                label_visibility="collapsed",
                            )
                        with add_col:
                            if st.button(
                                "➕ Add to my stock",
                                key=f"browse_add_{row['Product']}",
                                width="stretch",
                            ):
                                st.session_state.stock_df = add_to_stock(
                                    st.session_state.stock_df,
                                    row["Product"],
                                    int(qty),
                                )
                                st.toast(
                                    f"Added {int(qty)} × {row['Product']} to stock.",
                                    icon="🛒",
                                )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    with st.expander("📋 Full catalogue table"):
        st.dataframe(
            filtered if not filtered.empty else catalog,
            width="stretch",
            hide_index=True,
            column_config={
                "Cost (R)": st.column_config.NumberColumn(format="R%.2f"),
                "Median price (R)": st.column_config.NumberColumn(format="R%.2f"),
                "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    "<div class='footer'>iSpaza · Built for the IEB TechWays AI Hackathon 2026 · "
    "Team Grade 10</div>",
    unsafe_allow_html=True,
)
