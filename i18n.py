"""Tiny in-app i18n layer.

Strings live in ``data/i18n.json`` keyed by locale → key → text. The UI
calls ``t("some_key", **kwargs)`` from anywhere; the active locale is
read from Streamlit session state (falling back to English) unless the
caller passes ``locale=`` explicitly.

Locales supported:

* ``en`` — English
* ``zu`` — isiZulu
* ``xh`` — isiXhosa
* ``af`` — Afrikaans

Lookup is forgiving: missing key in the active locale falls back to the
English string, and if both are missing, the key itself is returned —
so a typo never breaks the page.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

I18N_PATH = Path(__file__).parent / "data" / "i18n.json"
DEFAULT_LOCALE = "en"

# Display names are written in the native script so the language picker
# is recognisable to a native speaker. Key order = picker order. The set
# covers all 11 official South African languages (SASL excluded — it's a
# signed language, not a text one).
LOCALES: dict[str, str] = {
    "en": "English",
    "af": "Afrikaans",
    "zu": "isiZulu",
    "xh": "isiXhosa",
    "nr": "isiNdebele",
    "ss": "siSwati",
    "st": "Sesotho",
    "nso": "Sesotho sa Leboa",
    "tn": "Setswana",
    "ve": "Tshivenḓa",
    "ts": "Xitsonga",
}


# Locales we maintain full translations for. Other locales are translated
# for the critical UI surface only; long body strings fall back to English.
CORE_LOCALES = frozenset({"en", "zu", "xh", "af"})

# The visible UI chrome — tabs, buttons, labels, status verbs. Every locale
# (including the partially-translated ones) must render these in-language.
CRITICAL_KEYS = frozenset({
    "language_label",
    "tagline_primary", "tagline_secondary",
    "sidebar_shop_details", "sidebar_shop_name", "sidebar_location",
    "sidebar_about_title",
    "tab_advice", "tab_profit", "tab_delivery", "tab_browse", "tab_help",
    "advice_stock_label", "advice_sales_label",
    "advice_button", "advice_style_label",
    "advice_style_worded", "advice_style_quick",
    "advice_heading",
    "advice_card_restock", "advice_card_pricing", "advice_card_add",
    "advice_confidence", "advice_report_problem", "advice_download_quick",
    "qa_dir_increase", "qa_dir_decrease", "qa_dir_hold",
    "qa_adjust_stock", "qa_adjust_price",
    "col_product", "col_reason", "col_priority",
    "col_supplier", "col_buy", "col_total",
    "schedule_mode_auto", "schedule_mode_manual", "schedule_mode_skip",
    "profit_subhead",
    "profit_kpi_revenue", "profit_kpi_cost", "profit_kpi_profit", "profit_kpi_margin",
    "profit_section_daily", "profit_section_units",
    "profit_units_by_product", "profit_units_by_day",
    "delivery_subhead",
    "delivery_section_plan", "delivery_section_trips",
    "delivery_section_next7", "delivery_section_reference",
    "delivery_section_supplier_notes",
    "delivery_supplier_delivers", "delivery_supplier_best_to_order",
    "delivery_supplier_lead_time", "delivery_supplier_transport",
    "delivery_supplier_products", "delivery_transport_free",
    "browse_subhead",
    "browse_search_label", "browse_filter_label",
    "browse_add_button", "browse_qty_label", "browse_no_match",
    "browse_full_table",
    "help_subhead", "help_new_ticket",
    "help_field_subject", "help_field_category", "help_field_priority",
    "help_field_description",
    "help_btn_submit", "help_btn_download", "help_btn_update_status",
    "help_your_tickets", "help_filter_status", "help_filter_all",
    "help_status_open", "help_status_in_progress", "help_status_resolved",
    "help_priority_low", "help_priority_medium", "help_priority_high",
    "help_cat_advice", "help_cat_pricing", "help_cat_delivery",
    "help_cat_bug", "help_cat_other",
    "auth_signin_title", "auth_signup_title",
    "auth_username", "auth_password",
    "auth_signin_btn", "auth_create_account_btn",
    "auth_have_account", "auth_need_account",
    "auth_failed", "auth_signed_in_as", "auth_signout_btn",
    "profit_current_stock_sales_section",
})


_cache: dict[str, dict[str, str]] | None = None


def _load() -> dict[str, dict[str, str]]:
    """Load the translation table from disk (memoised)."""
    global _cache
    if _cache is None:
        with I18N_PATH.open("r", encoding="utf-8") as f:
            _cache = json.load(f)
    return _cache


def _current_locale_from_session() -> str:
    """Read the locale from Streamlit session state with safe fallback."""
    try:
        import streamlit as st
        return str(st.session_state.get("locale", DEFAULT_LOCALE))
    except Exception:  # noqa: BLE001 - any import or context failure → English
        return DEFAULT_LOCALE


def current_locale() -> str:
    """Return the active locale code (e.g. ``"zu"``)."""
    loc = _current_locale_from_session()
    return loc if loc in LOCALES else DEFAULT_LOCALE


def t(key: str, locale: str | None = None, **fmt: Any) -> str:
    """Look up ``key`` in the active locale (or ``locale`` if given).

    If the key is missing in the active locale, fall back to English.
    If still missing, return the key itself so the caller sees the
    problem instead of a blank space. ``fmt`` is applied via ``str.format``.
    """
    if locale is None:
        locale = current_locale()
    elif locale not in LOCALES:
        locale = DEFAULT_LOCALE

    table = _load()
    text = (
        table.get(locale, {}).get(key)
        or table.get(DEFAULT_LOCALE, {}).get(key)
        or key
    )
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def all_keys() -> set[str]:
    """Every key defined in the English (canonical) table."""
    return set(_load().get(DEFAULT_LOCALE, {}).keys())


def reset_cache() -> None:
    """Drop the in-memory cache. Tests use this to re-read after edits."""
    global _cache
    _cache = None
