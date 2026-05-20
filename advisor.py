"""iSpaza advisor — deterministic, fully local recommender.

The "AI brain" runs entirely on the user's machine: no API key, no network,
no external service. It analyses the owner's actual stock and sales against
the township pricing benchmarks bundled in ``data/benchmarks.json``.

Output contract
---------------
``generate_advice_markdown`` returns:

    ## Restock this week
    ...
    ## Pricing adjustments
    ...
    ## One product to add
    ...
    *Confidence: Low | Medium | High*

``core.parse_advice_response`` consumes that markdown, the Streamlit UI
renders the three sections as cards, and the ledger entry records the run.

The signals the advisor reasons over
------------------------------------
For every product the owner names (in stock OR in sales):

* **sell_through** — units sold / (sold + remaining stock)
* **weeks_left**   — remaining stock / units sold per week
* **benchmark**    — the township price record (if we have one for the name)

These signals drive every recommendation. Nothing is hand-coded for a
specific product; change the inputs and the advice changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

from core import benchmarks_by_name


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ProductSignal:
    """One row in the owner's input, plus the derived numbers we reason on."""

    name: str                       # original casing — used in output
    key: str                        # lowercased — used for lookups
    stock: int
    sold: int
    sell_through: float             # 0.0–1.0
    weeks_left: float               # inf when stock>0 and sold==0; 0 when stock==0
    bench: dict[str, Any] | None    # the matching benchmark record, if any


def _clean_rows(df: pd.DataFrame, qty_col: str) -> Iterable[tuple[str, int]]:
    """Yield (product, qty) for non-blank rows; coerce qty to int (None → 0)."""
    if df is None or df.empty:
        return
    for _, row in df.iterrows():
        raw_name = row.get("Product")
        if raw_name is None or (isinstance(raw_name, float) and pd.isna(raw_name)):
            continue
        name = str(raw_name).strip()
        if not name or name.lower() == "nan":
            continue
        raw_qty = row.get(qty_col)
        if raw_qty is None or (isinstance(raw_qty, float) and pd.isna(raw_qty)):
            qty = 0
        else:
            try:
                qty = int(raw_qty)
            except (TypeError, ValueError):
                qty = 0
        yield name, qty


def _build_signals(
    stock_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    bench_index: dict[str, dict[str, Any]],
) -> list[_ProductSignal]:
    stock_map: dict[str, tuple[str, int]] = {}
    for name, qty in _clean_rows(stock_df, "Quantity"):
        stock_map[name.lower()] = (name, qty)

    sales_map: dict[str, tuple[str, int]] = {}
    for name, qty in _clean_rows(sales_df, "Units Sold"):
        sales_map[name.lower()] = (name, qty)

    signals: list[_ProductSignal] = []
    for key in sorted(set(stock_map) | set(sales_map)):
        name = stock_map.get(key, sales_map.get(key))[0]  # type: ignore[index]
        stock_qty = stock_map.get(key, ("", 0))[1]
        sold_qty = sales_map.get(key, ("", 0))[1]
        total = stock_qty + sold_qty
        sell_through = (sold_qty / total) if total > 0 else 0.0
        if sold_qty > 0:
            weeks_left = stock_qty / sold_qty
        else:
            weeks_left = float("inf") if stock_qty > 0 else 0.0
        signals.append(
            _ProductSignal(
                name=name,
                key=key,
                stock=stock_qty,
                sold=sold_qty,
                sell_through=sell_through,
                weeks_left=weeks_left,
                bench=bench_index.get(key),
            )
        )
    return signals


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _round_order(qty: int) -> int:
    """Round up to the nearest 5 — how owners actually order in cases/packs."""
    if qty <= 0:
        return 0
    return ((qty + 4) // 5) * 5


def _restock_section(signals: list[_ProductSignal]) -> str:
    """Rank reorderable products by urgency and write a 3–5 bullet list."""
    candidates: list[tuple[int, str]] = []
    for s in signals:
        if s.sold == 0:
            continue  # didn't move — don't reorder
        if s.stock == 0:
            urgency = 100
            qty = _round_order(max(int(s.sold * 1.5), 6))
            why = (
                f"sold out after {s.sold} units last week — "
                "customers will walk to the next shop"
            )
        elif s.weeks_left < 1:
            urgency = 80
            qty = _round_order(max(int(s.sold * 1.4), 6))
            why = (
                f"only {s.stock} left vs {s.sold} sold — under a week of cover"
            )
        elif s.sell_through >= 0.5 and s.sold >= 6:
            urgency = 60
            qty = _round_order(max(int(s.sold * 1.2), 6))
            why = (
                f"{int(s.sell_through * 100)}% sell-through — "
                "top up before the weekend rush"
            )
        elif s.weeks_left < 2:
            urgency = 40
            qty = _round_order(max(s.sold, 5))
            why = "around a week and a half of stock — reorder to stay ahead"
        else:
            continue

        candidates.append((urgency, f"- **{s.name}**: {qty} units — {why}."))

    candidates.sort(key=lambda c: -c[0])
    top = [b for _, b in candidates[:5]]

    if not top:
        return (
            "Stock levels look balanced against last week's sales — no urgent "
            "reorders today. Keep an eye on cold drinks and bread heading "
            "into the weekend; those spike the fastest."
        )
    return "\n".join(top)


def _pricing_section(signals: list[_ProductSignal]) -> str:
    """Two short levers: protect margin on top movers, free up slow stock."""
    hot = sorted(
        [s for s in signals if s.bench and s.sold >= 5 and s.sell_through >= 0.5],
        key=lambda s: -s.sold,
    )
    slow = sorted(
        [s for s in signals if s.bench and s.stock > 0 and s.sell_through < 0.3 and s.sold >= 1],
        key=lambda s: -s.stock,
    )

    tips: list[str] = []
    for s in hot[:2]:
        assert s.bench is not None
        lo, hi = s.bench["price_range_rand"]
        med = s.bench["median_price_rand"]
        tips.append(
            f"- **{s.name}** — top mover ({s.sold} sold). Township median is "
            f"R{med} (range R{lo}–R{hi}). If you're below R{med}, lift to it "
            "for one week and watch — you likely won't lose volume."
        )

    if slow[:1]:
        s = slow[0]
        assert s.bench is not None
        lo = s.bench["price_range_rand"][0]
        tips.append(
            f"- **{s.name}** — moved {s.sold} with {s.stock} still on the shelf. "
            f"Try a R{lo} promo for a week to free up space and pull in foot traffic."
        )

    if not tips:
        return (
            "No pricing changes needed this week. Your sell-through is "
            "balanced — nothing's flying off at a loss, nothing's stuck. Hold "
            "prices and re-check next week once you have another data point."
        )
    return "\n".join(tips)


def _add_product_section(
    signals: list[_ProductSignal],
    bench_index: dict[str, dict[str, Any]],
) -> str:
    """Vote on the best complement to the top sellers and pitch it."""
    stocked_keys = {s.key for s in signals if s.stock > 0 or s.sold > 0}
    top_sellers = sorted(
        [s for s in signals if s.sold > 0], key=lambda s: -s.sold
    )[:3]

    votes: dict[str, int] = {}
    for seller in top_sellers:
        if not seller.bench:
            continue
        for comp_name in seller.bench.get("complements", []):
            ck = comp_name.strip().lower()
            if ck in stocked_keys:
                continue
            if ck not in bench_index:
                # We only recommend products we can quote a benchmark price for.
                continue
            votes[ck] = votes.get(ck, 0) + seller.sold

    pick: dict[str, Any] | None = None
    if votes:
        winner_key = max(votes, key=lambda k: votes[k])
        pick = bench_index[winner_key]
    else:
        for fallback in (
            "Maggi 2-min noodles",
            "Brown bread loaf",
            "Lucky Star pilchards",
            "Fanta 500ml",
        ):
            fkey = fallback.lower()
            if fkey not in stocked_keys and fkey in bench_index:
                pick = bench_index[fkey]
                break

    if pick is None:
        return (
            "Hard to suggest a new product with this little data — log a "
            "couple more weeks of sales and iSpaza will spot what your "
            "customers want next."
        )

    name = pick["name"]
    cat = pick["category"]
    med = pick["median_price_rand"]
    lo = pick["price_range_rand"][0]
    starting_qty = {
        "snacks": 12,
        "soft drinks": 12,
        "staples": 10,
        "tinned food": 6,
        "household": 6,
    }.get(cat, 8)

    reason = {
        "snacks": (
            "pairs naturally with the cold drinks and impulse buys your "
            "customers already grab"
        ),
        "soft drinks": (
            "moves alongside snacks at lunch and after school"
        ),
        "staples": (
            "fills a household-basic slot with steady weekly demand — keeps "
            "customers from walking to a bigger shop"
        ),
        "tinned food": (
            "delivers high-margin protein that pairs with the bread you already "
            "sell well"
        ),
        "household": (
            "earns high margin even at low volume — gets picked up alongside "
            "groceries on payday"
        ),
    }.get(cat, "fits the product mix your customers already buy")

    wholesale_high = max(lo, (lo + med) // 2)
    return (
        f"**{name}** — try {starting_qty} units at R{med} retail (buy in around "
        f"R{lo}–R{wholesale_high}). It {reason}. Test rule: if you sell out in "
        "week one, double the order. If half is still on the shelf after two "
        "weeks, drop it — no harm done."
    )


def _confidence(signals: list[_ProductSignal]) -> str:
    """Confidence tracks how much usable data the owner gave us."""
    if not signals:
        return "Low"
    matched = sum(1 for s in signals if s.bench is not None)
    with_sales = sum(1 for s in signals if s.sold > 0)
    if matched >= 4 and with_sales >= 4:
        return "High"
    if matched >= 2 and with_sales >= 2:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_advice_markdown(
    shop_name: str,
    location: str,
    stock_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    benchmarks: dict[str, Any],
) -> str:
    """Return the three-section markdown the UI renders.

    The shop name and location are accepted so the call site reads naturally
    and so location-specific benchmarks can be added later; today the local
    rules don't branch on them.
    """
    del shop_name, location
    bench_index = benchmarks_by_name(benchmarks)
    signals = _build_signals(stock_df, sales_df, bench_index)

    restock = _restock_section(signals)
    pricing = _pricing_section(signals)
    add = _add_product_section(signals, bench_index)
    conf = _confidence(signals)

    return (
        f"## Restock this week\n{restock}\n\n"
        f"## Pricing adjustments\n{pricing}\n\n"
        f"## One product to add\n{add}\n\n"
        f"*Confidence: {conf}*"
    )
