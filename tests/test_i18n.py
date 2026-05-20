"""Unit tests for the i18n module."""

from __future__ import annotations

import re

import pytest

from i18n import (
    CORE_LOCALES,
    CRITICAL_KEYS,
    DEFAULT_LOCALE,
    LOCALES,
    all_keys,
    t,
)


def _strip_placeholders(s: str) -> str:
    """Remove ``{...}`` format placeholders so the test ignores pure templates."""
    return re.sub(r"\{[^}]*\}", "", s)


# ---------------------------------------------------------------------------
# Locale registry
# ---------------------------------------------------------------------------


def test_locales_include_every_official_sa_language():
    """All 11 official South African languages must be selectable."""
    expected = {
        "en", "af", "zu", "xh", "nr",
        "ss", "st", "nso", "tn", "ve", "ts",
    }
    assert set(LOCALES) == expected


def test_default_locale_is_english():
    assert DEFAULT_LOCALE == "en"


def test_locale_display_names_are_in_native_form():
    """The picker should read naturally to a native speaker."""
    assert LOCALES["zu"] == "isiZulu"
    assert LOCALES["xh"] == "isiXhosa"
    assert LOCALES["af"] == "Afrikaans"
    assert LOCALES["nr"] == "isiNdebele"
    assert LOCALES["ss"] == "siSwati"
    assert LOCALES["st"] == "Sesotho"
    assert LOCALES["nso"] == "Sesotho sa Leboa"
    assert LOCALES["tn"] == "Setswana"
    assert LOCALES["ve"] == "Tshivenḓa"
    assert LOCALES["ts"] == "Xitsonga"


# ---------------------------------------------------------------------------
# t() lookup
# ---------------------------------------------------------------------------


def test_t_returns_english_for_default_locale():
    assert t("tab_advice", locale="en") == "💡 Get Advice"


@pytest.mark.parametrize("locale", ["af", "zu", "xh"])
def test_core_locales_translate_every_english_key(locale):
    """Fully-maintained locales must translate every English key.

    A key counts as "translated" when its rendering in ``locale`` differs
    from English **after** format placeholders are stripped — that way a
    pure template like ``"{a} · {b}"`` doesn't fail this check.
    """
    missing: list[str] = []
    for key in all_keys():
        eng_stripped = _strip_placeholders(t(key, locale="en"))
        tgt_stripped = _strip_placeholders(t(key, locale=locale))
        if not any(c.isalpha() for c in eng_stripped):
            continue
        if eng_stripped == tgt_stripped:
            missing.append(key)
    assert not missing, (
        f"{locale} has {len(missing)} untranslated keys: {missing[:10]}..."
    )


@pytest.mark.parametrize("locale", ["nr", "ss", "st", "nso", "tn", "ve", "ts"])
def test_extended_locales_cover_critical_keys(locale):
    """Newer locales must at least translate the CRITICAL_KEYS surface.

    Long body strings (banners, help paragraphs) may fall back to English
    until native-speaker review lands — that's documented in the README.
    """
    missing: list[str] = []
    for key in CRITICAL_KEYS:
        eng_stripped = _strip_placeholders(t(key, locale="en"))
        tgt_stripped = _strip_placeholders(t(key, locale=locale))
        if not any(c.isalpha() for c in eng_stripped):
            continue
        if eng_stripped == tgt_stripped:
            missing.append(key)
    assert not missing, (
        f"{locale} is missing critical translations: {missing[:10]}..."
    )


def test_core_locales_set_is_a_subset_of_all_locales():
    assert CORE_LOCALES <= set(LOCALES)


def test_critical_keys_exist_in_english():
    """A CRITICAL_KEYS typo would silently exclude that key from the check."""
    keys_in_en = all_keys()
    missing = [k for k in CRITICAL_KEYS if k not in keys_in_en]
    assert not missing, f"CRITICAL_KEYS references unknown keys: {missing}"


def test_t_falls_back_to_english_when_key_missing_in_locale(monkeypatch):
    """If a translation file is missing a key, English is shown — never the raw key."""
    import i18n
    monkeypatch.setattr(
        i18n,
        "_cache",
        {
            "en": {"my_key": "English value"},
            "zu": {},  # zu intentionally missing my_key
        },
    )
    assert i18n.t("my_key", locale="zu") == "English value"


def test_t_returns_key_when_completely_missing(monkeypatch):
    import i18n
    monkeypatch.setattr(i18n, "_cache", {"en": {}, "zu": {}})
    assert i18n.t("not_a_real_key", locale="zu") == "not_a_real_key"


def test_t_unknown_locale_falls_back_to_english():
    assert t("tab_advice", locale="klingon") == t("tab_advice", locale="en")


# ---------------------------------------------------------------------------
# Format args
# ---------------------------------------------------------------------------


def test_t_substitutes_format_kwargs():
    # English string contains {qty} and {product}
    out = t("browse_add_toast", locale="en", qty=24, product="Niknaks 30g")
    assert "24" in out
    assert "Niknaks 30g" in out


def test_t_returns_raw_string_when_format_kwargs_missing():
    # Caller forgot to pass {qty} — we shouldn't raise; just return the template.
    out = t("browse_add_toast", locale="en")
    assert isinstance(out, str)
    assert "Added" in out  # English template contains 'Added'


# ---------------------------------------------------------------------------
# Smoke tests across all locales
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("locale", list(LOCALES))
def test_critical_ui_strings_are_non_empty_in_every_locale(locale):
    """If any of these are empty, the UI looks broken in that language."""
    critical = [
        "tab_advice", "tab_profit", "tab_delivery", "tab_browse",
        "advice_button", "advice_style_worded", "advice_style_quick",
        "qa_dir_increase", "qa_dir_decrease", "qa_dir_hold",
        "qa_adjust_stock", "qa_adjust_price",
        "schedule_mode_auto", "schedule_mode_manual", "schedule_mode_skip",
        "browse_add_button",
        "delivery_section_plan",
        "profit_subhead",
    ]
    for key in critical:
        value = t(key, locale=locale)
        assert value, f"locale={locale} key={key} is empty"
        # Should contain at least one alphabetic character (not just punctuation)
        assert any(c.isalpha() for c in value), f"{locale}/{key} has no letters: {value!r}"
