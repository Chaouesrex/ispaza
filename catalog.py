"""Product catalogue browsing and stock-add helpers.

Reads the benchmarks JSON and gives the UI three things:

* ``catalog_df(benchmarks)`` — every product as a single sortable
  DataFrame with cost / selling price / margin / supplier / pack size.
* ``filter_catalog(df, query, categories)`` — text search across product
  name and supplier plus a category multiselect filter. Both filters
  combine with AND semantics.
* ``add_to_stock(stock_df, name, quantity)`` — append-or-update a row
  in the owner's current-stock DataFrame from a catalogue pick.

The owner-facing column ordering puts margin and supplier up front so
the buying decision reads at a glance.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import pandas as pd


CATALOG_COLUMNS = [
    "Product",
    "Category",
    "Cost (R)",
    "Median price (R)",
    "Margin %",
    "Range (R)",
    "Supplier",
    "Best day",
    "Pack size",
    "Complements",
]


def catalog_df(benchmarks: dict[str, Any]) -> pd.DataFrame:
    """Return every catalogue product as a single DataFrame."""
    rows: list[dict[str, Any]] = []
    for p in benchmarks.get("products", []):
        cost = float(p.get("cost_price_rand", 0) or 0)
        median = float(p.get("median_price_rand", 0) or 0)
        margin = round((median - cost) / median * 100, 1) if median else 0.0
        lo, hi = p.get("price_range_rand", [0, 0])
        complements = ", ".join(p.get("complements", []))
        rows.append(
            {
                "Product": p["name"],
                "Category": p.get("category", "—"),
                "Cost (R)": round(cost, 2),
                "Median price (R)": round(median, 2),
                "Margin %": margin,
                "Range (R)": f"R{lo}–R{hi}",
                "Supplier": p.get("supplier", "—"),
                "Best day": p.get("best_purchase_day", "—"),
                "Pack size": int(p.get("wholesale_pack_size", 1) or 1),
                "Complements": complements,
            }
        )

    if not rows:
        return pd.DataFrame(columns=CATALOG_COLUMNS)
    return pd.DataFrame(rows, columns=CATALOG_COLUMNS)


def list_categories(benchmarks: dict[str, Any]) -> list[str]:
    """Sorted list of distinct product categories."""
    cats = {p.get("category", "—") for p in benchmarks.get("products", [])}
    return sorted(cats)


def filter_catalog(
    df: pd.DataFrame,
    query: str = "",
    categories: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Filter the catalogue by free-text search and selected categories.

    Both filters are case-insensitive. Empty query or empty/None
    categories means "no filter on that dimension".
    """
    if df.empty:
        return df

    out = df
    if query:
        q = query.strip().lower()
        if q:
            mask = (
                out["Product"].str.lower().str.contains(q, na=False)
                | out["Supplier"].str.lower().str.contains(q, na=False)
                | out["Category"].str.lower().str.contains(q, na=False)
            )
            out = out[mask]

    if categories:
        cat_set = {c for c in categories}
        if cat_set:
            out = out[out["Category"].isin(cat_set)]

    return out.reset_index(drop=True)


def add_to_stock(
    stock_df: pd.DataFrame,
    product: str,
    quantity: int,
) -> pd.DataFrame:
    """Add the product to the stock DataFrame (or increment if present).

    The match is case-insensitive on the product name. Returns a new
    DataFrame; the input is never mutated.
    """
    if not isinstance(product, str) or not product.strip():
        return stock_df.copy()
    quantity = max(int(quantity), 0)

    out = stock_df.copy() if stock_df is not None else pd.DataFrame(
        columns=["Product", "Quantity"]
    )
    if "Product" not in out.columns:
        out["Product"] = []
    if "Quantity" not in out.columns:
        out["Quantity"] = []

    key = product.strip().lower()
    existing_mask = out["Product"].astype(str).str.strip().str.lower() == key
    if existing_mask.any():
        idx = out.index[existing_mask][0]
        current = pd.to_numeric(out.at[idx, "Quantity"], errors="coerce")
        current = 0 if pd.isna(current) else int(current)
        out.at[idx, "Quantity"] = current + quantity
        return out.reset_index(drop=True)

    new_row = pd.DataFrame([{"Product": product.strip(), "Quantity": quantity}])
    return pd.concat([out, new_row], ignore_index=True)
