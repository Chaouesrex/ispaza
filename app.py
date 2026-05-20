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
from i18n import DEFAULT_LOCALE, LOCALES, t
from support import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    create_ticket,
    default_tickets,
    filter_by_status,
    tickets_to_csv,
    tickets_to_df,
    update_status,
)
from quick_actions import (
    DIR_DECREASE,
    DIR_HOLD,
    DIR_INCREASE,
    quick_actions_df,
    quick_actions_to_csv,
)
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
    f"""
    <div class="ispaza-header">
      <h1>iSpaza</h1>
      <div class="tagline">
        <span class="accent">{t("tagline_primary")}</span> {t("tagline_secondary")}
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

# Initialise locale BEFORE any t() call so the header tagline localises on first paint.
if "locale" not in st.session_state:
    st.session_state.locale = DEFAULT_LOCALE

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

if "tickets" not in st.session_state:
    st.session_state.tickets = default_tickets()

if "help_status_filter" not in st.session_state:
    st.session_state.help_status_filter = ""  # empty = All

if "show_report_form" not in st.session_state:
    st.session_state.show_report_form = False


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    locale_codes = list(LOCALES.keys())
    st.session_state.locale = st.selectbox(
        f"🌐 {t('language_label')}",
        options=locale_codes,
        format_func=lambda code: LOCALES[code],
        index=locale_codes.index(st.session_state.locale),
        key="locale_selector",
    )

    st.divider()

    st.markdown(f"### 🏪 {t('sidebar_shop_details')}")
    shop_name = st.text_input(t("sidebar_shop_name"), value="Mama Thandi's Spaza")
    location = st.text_input(t("sidebar_location"), value="Diepkloof, Soweto")

    st.divider()

    with st.expander(f"ℹ️ {t('sidebar_about_title')}"):
        st.markdown(t("sidebar_about_body"))

    st.divider()
    st.caption(t("sidebar_caption"))


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


def render_worded_advice(advice: Advice) -> None:
    cards = [
        (t("advice_card_restock"), advice.restock),
        (t("advice_card_pricing"), advice.pricing),
        (t("advice_card_add"), advice.add),
    ]
    for title, body in cards:
        with st.container(border=True):
            st.markdown(f"#### {title}")
            if body:
                st.markdown(body)
            else:
                st.caption(t("advice_no_section"))

    st.markdown(
        f"<div class='confidence-line'><em>{t('advice_confidence')}: "
        f"<strong>{advice.confidence}</strong></em></div>",
        unsafe_allow_html=True,
    )


def localize_quick_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Translate the Action and Adjust cell values into the active locale."""
    if df.empty:
        return df
    direction_map = {
        DIR_INCREASE: t("qa_dir_increase"),
        DIR_DECREASE: t("qa_dir_decrease"),
        DIR_HOLD: t("qa_dir_hold"),
    }
    adjust_map = {
        "Stock": t("qa_adjust_stock"),
        "Price": t("qa_adjust_price"),
        "—": t("qa_adjust_none"),
    }
    out = df.copy()
    out["Action"] = out["Action"].map(lambda v: direction_map.get(v, v))
    out["Adjust"] = out["Adjust"].map(lambda v: adjust_map.get(v, v))
    return out


def render_quick_actions(df: pd.DataFrame) -> None:
    if df.empty:
        st.info(t("advice_no_actions"))
        return

    localized = localize_quick_actions(df)
    st.dataframe(
        localized,
        width="stretch",
        hide_index=True,
        column_config={
            "Action": st.column_config.TextColumn(t("col_action"), width="small"),
            "Product": st.column_config.TextColumn(t("col_product"), width="medium"),
            "Adjust": st.column_config.TextColumn(t("col_adjust"), width="small"),
            "By": st.column_config.TextColumn(t("col_by"), width="small"),
            "Reason": st.column_config.TextColumn(t("col_reason"), width="large"),
            "Priority": st.column_config.ProgressColumn(
                t("col_priority"),
                min_value=0,
                max_value=100,
                format="%d",
                width="small",
            ),
        },
    )
    st.download_button(
        t("advice_download_quick"),
        data=quick_actions_to_csv(localized),
        file_name=f"ispaza_quick_actions_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_advice, tab_profit, tab_delivery, tab_browse, tab_help = st.tabs(
    [
        t("tab_advice"),
        t("tab_profit"),
        t("tab_delivery"),
        t("tab_browse"),
        t("tab_help"),
    ]
)


# ----- Tab 1: Get Advice ---------------------------------------------------


with tab_advice:
    st.subheader(t("advice_subhead"))

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown(f"**{t('advice_stock_label')}**")
        st.caption(t("advice_stock_caption"))
        st.session_state.stock_df = st.data_editor(
            st.session_state.stock_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn(
                    t("col_product"), required=True, width="medium"
                ),
                "Quantity": st.column_config.NumberColumn(
                    t("col_quantity"), min_value=0, step=1, format="%d"
                ),
            },
            key="stock_editor",
        )

    with right:
        st.markdown(f"**{t('advice_sales_label')}**")
        st.caption(t("advice_sales_caption"))
        st.session_state.sales_df = st.data_editor(
            st.session_state.sales_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn(
                    t("col_product"), required=True, width="medium"
                ),
                "Units Sold": st.column_config.NumberColumn(
                    t("col_units_sold"), min_value=0, step=1, format="%d"
                ),
            },
            key="sales_editor",
        )

    st.write("")

    # Map localized labels back to internal mode keys so changing language
    # doesn't reset the user's mode choice.
    worded_label = t("advice_style_worded")
    quick_label = t("advice_style_quick")
    mode_to_label = {"Worded advice": worded_label, "Quick actions": quick_label}
    label_to_mode = {v: k for k, v in mode_to_label.items()}
    current_label = mode_to_label.get(st.session_state.advice_mode, worded_label)

    mode_col, btn_col = st.columns([2, 1])
    with mode_col:
        chosen_label = st.radio(
            t("advice_style_label"),
            [worded_label, quick_label],
            horizontal=True,
            index=[worded_label, quick_label].index(current_label),
            help=t("advice_style_help"),
            key="advice_mode_radio",
        )
        st.session_state.advice_mode = label_to_mode[chosen_label]
    with btn_col:
        st.write("")
        clicked = st.button(t("advice_button"), type="primary", width="stretch")

    if clicked:
        try:
            benchmarks = cached_benchmarks()
            with st.spinner(t("advice_thinking")):
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
        st.markdown(f"### {t('advice_heading')}")
        if st.session_state.advice_mode == "Worded advice" and has_worded:
            render_worded_advice(st.session_state.latest_advice)
        elif st.session_state.advice_mode == "Quick actions" and has_quick:
            render_quick_actions(st.session_state.latest_quick_df)

        # Report-a-problem affordance — creates a support ticket pre-filled
        # with the advice context so the owner doesn't have to retype.
        st.write("")
        if st.button(
            t("advice_report_problem"),
            key="advice_report_btn",
            type="secondary",
        ):
            st.session_state.show_report_form = not st.session_state.show_report_form

        if st.session_state.show_report_form:
            with st.form("advice_report_form", border=True, clear_on_submit=True):
                st.markdown(f"**{t('advice_report_problem')}**")
                report_subject = st.text_input(
                    t("help_field_subject"),
                    value=t("report_default_subject"),
                    key="advice_report_subject",
                )
                report_description = st.text_area(
                    t("help_field_description"),
                    placeholder="What was wrong with the advice?",
                    key="advice_report_description",
                    height=100,
                )
                report_priority_label = st.selectbox(
                    t("help_field_priority"),
                    options=[t("help_priority_low"), t("help_priority_medium"), t("help_priority_high")],
                    index=1,
                    key="advice_report_priority",
                )
                priority_key_by_label = {
                    t("help_priority_low"): "low",
                    t("help_priority_medium"): "medium",
                    t("help_priority_high"): "high",
                }
                submitted = st.form_submit_button(t("help_btn_submit"), type="primary")
                if submitted:
                    try:
                        new = create_ticket(
                            subject=report_subject,
                            description=report_description,
                            category="advice",
                            priority=priority_key_by_label.get(report_priority_label, "medium"),
                            locale=st.session_state.locale,
                            context={
                                "source": "advice_tab",
                                "advice_mode": st.session_state.advice_mode,
                                "confidence": (
                                    st.session_state.latest_advice.confidence
                                    if st.session_state.latest_advice is not None
                                    else None
                                ),
                            },
                            existing=st.session_state.tickets,
                        )
                        st.session_state.tickets.append(new)
                        st.session_state.show_report_form = False
                        st.toast(
                            t("help_toast_submitted", id=new.id),
                            icon="🆘",
                        )
                    except ValueError as e:
                        st.error(str(e))


# ----- Tab 2: Profit Tracker ----------------------------------------------


with tab_profit:
    st.subheader(t("profit_subhead"))

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
    k1.metric(t("profit_kpi_revenue"), f"R{rev:,.2f}")
    k2.metric(t("profit_kpi_cost"), f"R{cog:,.2f}")
    k3.metric(t("profit_kpi_profit"), f"R{profit:,.2f}")
    k4.metric(t("profit_kpi_margin"), f"{margin:.1f}%")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    chart_col, breakdown_col = st.columns([3, 2], gap="large")

    with chart_col:
        st.markdown(f"#### {t('profit_section_daily')}")
        running = running_totals(sales_records)
        if running.empty:
            st.info(t("profit_no_chart"))
        else:
            chart_df = running.set_index("Date")[["Profit (R)", "Cumulative Profit (R)"]]
            st.line_chart(chart_df, height=320, color=[PRIMARY_GREEN, ACCENT_YELLOW])
            st.caption(t("profit_chart_caption"))

    with breakdown_col:
        st.markdown(f"#### {t('profit_section_per_product')}")
        per_product = product_profit_breakdown(sales_records)
        if per_product.empty:
            st.info(t("profit_no_breakdown"))
        else:
            st.dataframe(
                per_product,
                width="stretch",
                hide_index=True,
                column_config={
                    "Product": st.column_config.TextColumn(t("col_product")),
                    "Units": st.column_config.NumberColumn(t("col_units")),
                    "Profit (R)": st.column_config.NumberColumn(t("col_profit"), format="R%.2f"),
                    "Revenue (R)": st.column_config.NumberColumn(t("col_revenue"), format="R%.2f"),
                    "Cost (R)": st.column_config.NumberColumn(t("col_cost"), format="R%.2f"),
                    "Margin %": st.column_config.NumberColumn(t("col_margin_pct"), format="%.1f%%"),
                },
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"#### {t('profit_section_units')}")
    units_col_a, units_col_b = st.columns(2, gap="large")
    with units_col_a:
        st.markdown(t("profit_units_by_product"))
        by_product = units_by_product(sales_records)
        if by_product.empty:
            st.info(t("profit_no_units"))
        else:
            st.bar_chart(
                by_product.set_index("Product")["Units"],
                height=300,
                color=PRIMARY_GREEN,
            )
    with units_col_b:
        st.markdown(t("profit_units_by_day"))
        pivot = units_pivot_by_day(sales_records)
        if pivot.empty:
            st.info(t("profit_no_units"))
        else:
            st.bar_chart(pivot, stack=True, height=300)
            st.caption(t("profit_units_by_day_hint"))

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"#### {t('profit_section_daily_breakdown')}")
    daily = daily_profit_breakdown(sales_records)
    if daily.empty:
        st.info(t("profit_no_daily"))
    else:
        st.dataframe(
            daily,
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn(t("col_date")),
                "Units": st.column_config.NumberColumn(t("col_units")),
                "Revenue (R)": st.column_config.NumberColumn(t("col_revenue"), format="R%.2f"),
                "Cost (R)": st.column_config.NumberColumn(t("col_cost"), format="R%.2f"),
                "Profit (R)": st.column_config.NumberColumn(t("col_profit"), format="R%.2f"),
                "Margin %": st.column_config.NumberColumn(t("col_margin_pct"), format="%.1f%%"),
            },
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    log_left, log_right = st.columns(2, gap="large")

    with log_left:
        st.markdown(f"**{t('profit_sales_log')}**")
        st.caption(t("profit_sales_log_caption"))
        st.session_state.sales_log_df = st.data_editor(
            st.session_state.sales_log_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn(t("col_date"), help="YYYY-MM-DD"),
                "Product": st.column_config.TextColumn(t("col_product"), required=True),
                "Units": st.column_config.NumberColumn(
                    t("col_units"), min_value=0, step=1, format="%d"
                ),
                "Unit Price (R)": st.column_config.NumberColumn(
                    t("col_unit_price"), min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Unit Cost (R)": st.column_config.NumberColumn(
                    t("col_unit_cost"), min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Revenue (R)": st.column_config.NumberColumn(
                    t("col_revenue"), format="R%.2f", disabled=True
                ),
                "Cost (R)": st.column_config.NumberColumn(
                    t("col_cost"), format="R%.2f", disabled=True
                ),
                "Profit (R)": st.column_config.NumberColumn(
                    t("col_profit"), format="R%.2f", disabled=True
                ),
            },
            key="sales_log_editor",
        )
        st.download_button(
            t("profit_download_sales"),
            data=st.session_state.sales_log_df.to_csv(index=False).encode("utf-8"),
            file_name=f"ispaza_sales_{date.today().isoformat()}.csv",
            mime="text/csv",
        )

    with log_right:
        st.markdown(f"**{t('profit_purchase_log')}**")
        st.caption(t("profit_purchase_log_caption"))
        st.session_state.purchase_log_df = st.data_editor(
            st.session_state.purchase_log_df,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            column_config={
                "Date": st.column_config.TextColumn(t("col_date"), help="YYYY-MM-DD"),
                "Product": st.column_config.TextColumn(t("col_product"), required=True),
                "Quantity": st.column_config.NumberColumn(
                    t("col_quantity"), min_value=0, step=1, format="%d"
                ),
                "Unit Cost (R)": st.column_config.NumberColumn(
                    t("col_unit_cost"), min_value=0.0, step=0.5, format="R%.2f"
                ),
                "Total Cost (R)": st.column_config.NumberColumn(
                    t("col_total_cost"), format="R%.2f", disabled=True
                ),
                "Supplier": st.column_config.TextColumn(t("col_supplier")),
            },
            key="purchase_log_editor",
        )
        st.download_button(
            t("profit_download_purchases"),
            data=st.session_state.purchase_log_df.to_csv(index=False).encode("utf-8"),
            file_name=f"ispaza_purchases_{date.today().isoformat()}.csv",
            mime="text/csv",
        )


# ----- Tab 3: Delivery & Purchasing ----------------------------------------


with tab_delivery:
    st.subheader(t("delivery_subhead"))

    benchmarks = cached_benchmarks()
    suppliers = cached_suppliers()
    today = date.today()

    stocked_products = list(st.session_state.stock_df.get("Product", []))

    st.markdown(
        f"""
        <div class="info-banner accent">
          {t("delivery_banner")}
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

    st.markdown(f"#### {t('delivery_section_plan')}")
    if plan.empty:
        st.success(t("delivery_nothing_urgent"))
        st.session_state.schedule_overrides = {}
    else:
        plan_for_editor = plan.copy()
        plan_for_editor["Scheduled date"] = pd.to_datetime(
            plan_for_editor["Scheduled date"]
        )

        # Map internal mode values to localized labels so the dropdown
        # shows the user's language; we map back before persisting.
        mode_to_label = {
            "Auto": t("schedule_mode_auto"),
            "Manual": t("schedule_mode_manual"),
            "Skip": t("schedule_mode_skip"),
        }
        label_to_mode = {v: k for k, v in mode_to_label.items()}
        plan_for_editor["Mode"] = plan_for_editor["Mode"].map(
            lambda m: mode_to_label.get(m, m)
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
                "Product": st.column_config.TextColumn(t("col_product")),
                "Buy": st.column_config.TextColumn(t("col_buy"), width="small"),
                "Unit cost (R)": st.column_config.NumberColumn(
                    t("col_unit_cost"), format="R%.2f"
                ),
                "Est. cost (R)": st.column_config.NumberColumn(
                    t("col_line_cost"), format="R%.2f"
                ),
                "Supplier": st.column_config.TextColumn(t("col_supplier"), width="medium"),
                "Channel": st.column_config.TextColumn(t("col_channel"), width="small"),
                "Best day": st.column_config.TextColumn(t("col_best_day"), width="small"),
                "Next date": st.column_config.TextColumn(
                    t("col_next_date"), width="small", help=t("schedule_auto_date_help")
                ),
                "Mode": st.column_config.SelectboxColumn(
                    t("col_mode"),
                    options=list(mode_to_label.values()),
                    required=True,
                    width="small",
                    help=t("schedule_mode_help"),
                ),
                "Scheduled date": st.column_config.DateColumn(
                    t("col_scheduled_date"),
                    width="small",
                    format="YYYY-MM-DD",
                    help=t("schedule_date_help"),
                ),
                "Reason": st.column_config.TextColumn(t("col_reason"), width="large"),
                "Urgency": st.column_config.ProgressColumn(
                    t("col_urgency"), min_value=0, max_value=100, format="%d", width="small"
                ),
            },
            column_order=[
                "Product", "Buy", "Unit cost (R)", "Est. cost (R)",
                "Supplier", "Mode", "Scheduled date", "Best day",
                "Next date", "Reason", "Urgency",
            ],
        )
        # Map localized mode labels back to internal values before processing.
        edited_plan = edited_plan.copy()
        edited_plan["Mode"] = edited_plan["Mode"].map(
            lambda lbl: label_to_mode.get(lbl, lbl)
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
        skip_note = t("delivery_caption_skipped", n=skipped_count) if skipped_count else ""
        st.caption(
            t(
                "delivery_caption_summary",
                included=included_count,
                skip_note=skip_note,
                stock=totals["stock"],
                transport=totals["transport"],
                total=totals["total"],
            )
        )

        st.download_button(
            t("delivery_download_plan"),
            data=schedule_to_csv(plan_for_totals),
            file_name=f"ispaza_purchase_plan_{today.isoformat()}.csv",
            mime="text/csv",
        )

        st.markdown(f"#### {t('delivery_section_trips')}")
        st.caption(t("delivery_section_trips_caption"))
        trips = trip_summary(plan_for_totals, suppliers=suppliers)
        if trips.empty:
            st.info(t("delivery_all_skipped"))
        else:
            st.dataframe(
                trips,
                width="stretch",
                hide_index=True,
                column_config={
                    "Scheduled date": st.column_config.TextColumn(t("col_scheduled_date")),
                    "Best day": st.column_config.TextColumn(t("col_best_day")),
                    "Supplier": st.column_config.TextColumn(t("col_supplier")),
                    "Items": st.column_config.TextColumn(t("col_items")),
                    "Stock cost (R)": st.column_config.NumberColumn(
                        t("col_stock_cost"), format="R%.2f"
                    ),
                    "Transport (R)": st.column_config.NumberColumn(
                        t("col_transport"), format="R%.2f"
                    ),
                    "Total (R)": st.column_config.NumberColumn(t("col_total"), format="R%.2f"),
                },
            )
            st.markdown(
                "<div class='info-banner'>"
                + t(
                    "delivery_grand_total_html",
                    total=totals["total"],
                    stock=totals["stock"],
                    transport=totals["transport"],
                )
                + "</div>",
                unsafe_allow_html=True,
            )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"#### {t('delivery_section_next7')}")
    upcoming = upcoming_deliveries(
        today,
        benchmarks,
        products_in_shop=stocked_products if stocked_products else None,
    )
    st.dataframe(
        upcoming,
        width="stretch",
        hide_index=True,
        column_config={
            "Date": st.column_config.TextColumn(t("col_date")),
            "Day": st.column_config.TextColumn(t("col_day")),
            "Deliveries arriving": st.column_config.TextColumn(t("col_deliveries_arriving")),
            "Best to order / buy": st.column_config.TextColumn(t("col_best_to_order")),
        },
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"#### {t('delivery_section_reference')}")
    schedule = weekly_schedule(
        benchmarks,
        products_in_shop=stocked_products if stocked_products else None,
    )
    st.dataframe(
        schedule,
        width="stretch",
        hide_index=True,
        column_config={
            "Day": st.column_config.TextColumn(t("col_day")),
            "Deliveries arriving": st.column_config.TextColumn(t("col_deliveries_arriving")),
            "Best to order / buy": st.column_config.TextColumn(t("col_best_to_order")),
        },
    )
    st.download_button(
        t("delivery_download_schedule"),
        data=schedule_to_csv(schedule),
        file_name=f"ispaza_weekly_schedule_{today.isoformat()}.csv",
        mime="text/csv",
    )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.markdown(f"#### {t('delivery_section_supplier_notes')}")
    for sup in suppliers.get("suppliers", []):
        with st.container(border=True):
            channel = sup["channel"].replace("_", " ")
            days = ", ".join(sup.get("delivery_days", [])) or "—"
            transport = float(sup.get("transport_cost_rand", 0) or 0)
            min_order = float(sup.get("min_order_rand", 0) or 0)
            lead_days = int(sup.get("lead_time_days", 0))
            transport_str = f"R{transport:.0f}" if transport else t("delivery_transport_free")
            min_order_str = (
                t("delivery_min_order_value", value=min_order)
                if min_order
                else t("delivery_min_order_none")
            )
            st.markdown(
                f"**{sup['name']}** · _{channel}_  \n"
                f"**{t('delivery_supplier_delivers')}:** {days} · "
                f"**{t('delivery_supplier_best_to_order')}:** "
                f"{sup.get('best_order_day', '—')} · "
                f"**{t('delivery_supplier_lead_time')}:** "
                f"{lead_days} day{'s' if lead_days != 1 else ''}  \n"
                f"**{t('delivery_supplier_transport')}:** {transport_str} · {min_order_str}"
            )
            products_line = ", ".join(sup.get("products", []))
            if products_line:
                st.caption(f"{t('delivery_supplier_products')}: {products_line}")
            notes = sup.get("notes")
            if notes:
                st.markdown(f"_{notes}_")


# ----- Tab 4: Browse Products ----------------------------------------------


with tab_browse:
    st.subheader(t("browse_subhead"))

    catalog = cached_catalog_df()
    categories = list_categories(cached_benchmarks())

    st.markdown(
        f"""
        <div class="info-banner accent">
          {t("browse_banner", count=len(catalog), cats=len(categories))}
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_col, cat_col = st.columns([3, 4], gap="large")
    with search_col:
        st.session_state.browse_query = st.text_input(
            t("browse_search_label"),
            value=st.session_state.browse_query,
            placeholder=t("browse_search_placeholder"),
            key="browse_query_input",
        )
    with cat_col:
        st.session_state.browse_categories = st.multiselect(
            t("browse_filter_label"),
            options=categories,
            default=st.session_state.browse_categories,
            key="browse_categories_input",
        )

    filtered = filter_catalog(
        catalog,
        query=st.session_state.browse_query,
        categories=st.session_state.browse_categories,
    )

    count_caption = t("browse_count_caption", shown=len(filtered), total=len(catalog))
    if len(filtered) < len(catalog):
        count_caption += t("browse_count_clear_hint")
    st.caption(count_caption)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    if filtered.empty:
        st.warning(t("browse_no_match"))
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
                            f"{t('browse_card_cost_margin', cost=row['Cost (R)'], margin=row['Margin %'])}"
                            f"</span></div>"
                            f"<div class='meta'>"
                            f"{t('browse_card_category_range', category=row['Category'].title(), range=row['Range (R)'])}"
                            f"</div>"
                            f"<div class='meta'>"
                            f"{t('browse_card_supplier', supplier=row['Supplier'])}"
                            f"</div>"
                            f"<div class='meta'>"
                            f"{t('browse_card_best_pack', best_day=row['Best day'], pack_size=row['Pack size'])}"
                            f"</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                        add_col, qty_col = st.columns([3, 2])
                        with qty_col:
                            qty = st.number_input(
                                t("browse_qty_label"),
                                min_value=1,
                                value=int(row["Pack size"]),
                                step=1,
                                key=f"browse_qty_{row['Product']}",
                                label_visibility="collapsed",
                            )
                        with add_col:
                            if st.button(
                                t("browse_add_button"),
                                key=f"browse_add_{row['Product']}",
                                width="stretch",
                            ):
                                st.session_state.stock_df = add_to_stock(
                                    st.session_state.stock_df,
                                    row["Product"],
                                    int(qty),
                                )
                                st.toast(
                                    t("browse_add_toast", qty=int(qty), product=row["Product"]),
                                    icon="🛒",
                                )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    with st.expander(t("browse_full_table")):
        st.dataframe(
            filtered if not filtered.empty else catalog,
            width="stretch",
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn(t("col_product")),
                "Category": st.column_config.TextColumn(t("col_category")),
                "Cost (R)": st.column_config.NumberColumn(t("col_cost"), format="R%.2f"),
                "Median price (R)": st.column_config.NumberColumn(t("col_median_price"), format="R%.2f"),
                "Margin %": st.column_config.NumberColumn(t("col_margin_pct"), format="%.1f%%"),
                "Range (R)": st.column_config.TextColumn(t("col_range")),
                "Supplier": st.column_config.TextColumn(t("col_supplier")),
                "Best day": st.column_config.TextColumn(t("col_best_day")),
                "Pack size": st.column_config.NumberColumn(t("col_pack_size")),
                "Complements": st.column_config.TextColumn(t("col_complements")),
            },
        )


# ----- Tab 5: Help & Reports -----------------------------------------------


with tab_help:
    st.subheader(t("help_subhead"))

    st.markdown(
        f"<div class='info-banner accent'>{t('help_intro')}</div>",
        unsafe_allow_html=True,
    )

    # Localised <-> internal mappings for the form controls.
    cat_to_label = {
        "advice": t("help_cat_advice"),
        "pricing": t("help_cat_pricing"),
        "delivery": t("help_cat_delivery"),
        "bug": t("help_cat_bug"),
        "other": t("help_cat_other"),
    }
    label_to_cat = {v: k for k, v in cat_to_label.items()}

    pri_to_label = {
        "low": t("help_priority_low"),
        "medium": t("help_priority_medium"),
        "high": t("help_priority_high"),
    }
    label_to_pri = {v: k for k, v in pri_to_label.items()}

    status_to_label = {
        "open": t("help_status_open"),
        "in_progress": t("help_status_in_progress"),
        "resolved": t("help_status_resolved"),
    }
    label_to_status = {v: k for k, v in status_to_label.items()}

    # ----- New ticket form -------------------------------------------------

    with st.form("new_ticket_form", border=True, clear_on_submit=True):
        st.markdown(f"#### {t('help_new_ticket')}")
        new_subject = st.text_input(t("help_field_subject"))
        cat_col, pri_col = st.columns(2)
        with cat_col:
            new_cat_label = st.selectbox(
                t("help_field_category"),
                options=list(cat_to_label.values()),
                index=4,  # default to "Other"
            )
        with pri_col:
            new_pri_label = st.selectbox(
                t("help_field_priority"),
                options=list(pri_to_label.values()),
                index=1,  # default to medium
            )
        new_description = st.text_area(t("help_field_description"), height=120)
        submitted_new = st.form_submit_button(t("help_btn_submit"), type="primary")
        if submitted_new:
            try:
                new_t = create_ticket(
                    subject=new_subject,
                    description=new_description,
                    category=label_to_cat.get(new_cat_label, "other"),
                    priority=label_to_pri.get(new_pri_label, "medium"),
                    locale=st.session_state.locale,
                    existing=st.session_state.tickets,
                )
                st.session_state.tickets.append(new_t)
                st.toast(t("help_toast_submitted", id=new_t.id), icon="🆘")
            except ValueError:
                st.error(t("help_subject_required"))

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ----- Ticket list + status filter ------------------------------------

    list_col, filter_col = st.columns([3, 1])
    with list_col:
        st.markdown(f"#### {t('help_your_tickets')}")
    with filter_col:
        filter_choices = [t("help_filter_all")] + list(status_to_label.values())
        chosen_filter = st.selectbox(
            t("help_filter_status"),
            options=filter_choices,
            index=0,
            label_visibility="visible",
        )
        active_status = (
            label_to_status[chosen_filter]
            if chosen_filter in label_to_status
            else None
        )

    visible_tickets = filter_by_status(st.session_state.tickets, active_status)

    if not visible_tickets:
        st.info(t("help_no_tickets"))
    else:
        # Render each ticket as a card with subject, badges, body, and an
        # "Update status" button that cycles open → in_progress → resolved.
        for tk in sorted(
            visible_tickets,
            key=lambda x: ({"high": 0, "medium": 1, "low": 2}.get(x.priority, 99),
                           -x.created.timestamp()),
        ):
            status_pill = status_to_label.get(tk.status, tk.status)
            priority_pill = pri_to_label.get(tk.priority, tk.priority)
            category_pill = cat_to_label.get(tk.category, tk.category)
            with st.container(border=True):
                top_l, top_r = st.columns([4, 1])
                with top_l:
                    st.markdown(
                        f"**#{tk.id} · {tk.subject}**  \n"
                        f"<span style='color:#555;font-size:0.85rem'>"
                        f"{category_pill} · {priority_pill} · "
                        f"{status_pill} · {tk.created.strftime('%Y-%m-%d %H:%M')}"
                        f"</span>",
                        unsafe_allow_html=True,
                    )
                with top_r:
                    if st.button(
                        t("help_btn_update_status"),
                        key=f"help_status_btn_{tk.id}",
                        width="stretch",
                    ):
                        st.session_state.tickets = update_status(
                            st.session_state.tickets, tk.id
                        )
                        st.rerun()
                if tk.description:
                    st.markdown(tk.description)
                if tk.context:
                    with st.expander("Context"):
                        st.json(tk.context)

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    st.download_button(
        t("help_btn_download"),
        data=tickets_to_csv(st.session_state.tickets),
        file_name=f"ispaza_tickets_{date.today().isoformat()}.csv",
        mime="text/csv",
    )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown(
    f"<div class='footer'>{t('footer')}</div>",
    unsafe_allow_html=True,
)
