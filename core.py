"""Pure-logic helpers for iSpaza.

Anything that does not require Streamlit lives here so it can be unit-tested
without spinning up a UI. app.py imports these helpers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

BENCHMARKS_PATH = Path(__file__).parent / "data" / "benchmarks.json"
SUPPLIERS_PATH = Path(__file__).parent / "data" / "suppliers.json"

DAYS_OF_WEEK = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

SECTION_TITLES = {
    "restock": "Restock this week",
    "pricing": "Pricing adjustments",
    "add": "One product to add",
}


@dataclass
class Advice:
    """Parsed iSpaza response, ready for the UI to render."""

    restock: str
    pricing: str
    add: str
    confidence: str  # "Low", "Medium", "High", or "Unknown"
    raw: str


def load_benchmarks(path: Path | str | None = None) -> dict[str, Any]:
    """Load the local pricing benchmark JSON."""
    target = Path(path) if path else BENCHMARKS_PATH
    with target.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_suppliers(path: Path | str | None = None) -> dict[str, Any]:
    """Load the supplier directory JSON."""
    target = Path(path) if path else SUPPLIERS_PATH
    with target.open("r", encoding="utf-8") as f:
        return json.load(f)


def benchmarks_by_name(benchmarks: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the benchmarks list by case-insensitive product name."""
    return {p["name"].lower(): p for p in benchmarks.get("products", [])}


def suppliers_by_name(suppliers: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index the suppliers list by case-insensitive name."""
    return {s["name"].lower(): s for s in suppliers.get("suppliers", [])}


def default_stock() -> pd.DataFrame:
    """Realistic pre-fill for the Current Stock data editor."""
    return pd.DataFrame(
        [
            {"Product": "Niknaks 30g", "Quantity": 22},
            {"Product": "White bread loaf", "Quantity": 0},
            {"Product": "Coca-Cola 500ml", "Quantity": 8},
            {"Product": "Simba chips 36g", "Quantity": 15},
            {"Product": "Sunlight bar soap", "Quantity": 6},
        ]
    )


def default_sales() -> pd.DataFrame:
    """Realistic pre-fill for the Last Week's Sales data editor."""
    return pd.DataFrame(
        [
            {"Product": "Niknaks 30g", "Units Sold": 18},
            {"Product": "White bread loaf", "Units Sold": 20},
            {"Product": "Coca-Cola 500ml", "Units Sold": 24},
            {"Product": "Simba chips 36g", "Units Sold": 9},
            {"Product": "Sunlight bar soap", "Units Sold": 2},
        ]
    )


def clean_df(df: pd.DataFrame, qty_col: str) -> pd.DataFrame:
    """Drop empty rows, coerce types, and trim whitespace."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["Product", qty_col])
    out = df.copy()
    out["Product"] = out["Product"].astype(str).str.strip()
    out = out[out["Product"].astype(bool) & (out["Product"].str.lower() != "nan")]
    out[qty_col] = pd.to_numeric(out[qty_col], errors="coerce").fillna(0).astype(int)
    return out.reset_index(drop=True)


# Back-compat alias for callers that still use the private name.
_clean_df = clean_df


def _header_pattern(title: str) -> re.Pattern[str]:
    return re.compile(rf"^##\s*{re.escape(title)}\s*$", re.IGNORECASE | re.MULTILINE)


def parse_advice_response(text: str) -> Advice:
    """Split the advisor's markdown response into the three sections + confidence.

    Tolerant of:
    - Extra whitespace around headers
    - Mixed case in section titles
    - Missing sections (returns empty string for that section)
    - Confidence line variants like "Confidence: High" or "*Confidence: High*"
    """
    raw = (text or "").strip()

    boundaries: list[tuple[str, int, int]] = []
    for key, title in SECTION_TITLES.items():
        m = _header_pattern(title).search(raw)
        if m:
            boundaries.append((key, m.start(), m.end()))
    boundaries.sort(key=lambda b: b[1])

    sections = {"restock": "", "pricing": "", "add": ""}
    for i, (key, _, end) in enumerate(boundaries):
        next_start = boundaries[i + 1][1] if i + 1 < len(boundaries) else len(raw)
        sections[key] = raw[end:next_start].strip()

    confidence = "Unknown"
    conf_match = re.search(
        r"confidence\s*[:\-]\s*(low|medium|high)",
        raw,
        re.IGNORECASE,
    )
    if conf_match:
        confidence = conf_match.group(1).capitalize()

    for key in sections:
        sections[key] = _strip_trailing_confidence(sections[key])

    return Advice(
        restock=sections["restock"],
        pricing=sections["pricing"],
        add=sections["add"],
        confidence=confidence,
        raw=raw,
    )


def _strip_trailing_confidence(section: str) -> str:
    """Confidence line may land at the bottom of the last section — pull it off."""
    lines = section.rstrip().splitlines()
    while lines and re.search(
        r"confidence\s*[:\-]\s*(low|medium|high)", lines[-1], re.IGNORECASE
    ):
        lines.pop()
    return "\n".join(lines).rstrip()


def total_units(df: pd.DataFrame, qty_col: str) -> int:
    cleaned = clean_df(df, qty_col)
    if cleaned.empty:
        return 0
    return int(cleaned[qty_col].sum())
