"""Quick-action recommendations — the terse counterpart to advisor.py.

Where ``advisor.generate_advice_markdown`` writes paragraphs, this module
produces a single sortable table: one row per signal with a direction
(Increase / Decrease / Hold), what to adjust (Stock / Price), the
specific amount, and a one-line reason. Built for shop owners who don't
want to read — they want to know what to do *right now*.

Three directions, each tied to an icon the UI renders directly:

    ⬆️ Increase   — buy more stock, or lift the price
    ⬇️ Decrease   — drop the price to clear slow stock
    ⏸️ Hold       — balanced; no change indicated

The output is a ``pandas.DataFrame`` so ``st.dataframe`` can render it
natively, sort it, and let the owner download a CSV in one click.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from advisor import _build_signals, _ProductSignal, _round_order
from core import benchmarks_by_name


# Direction labels — these strings are what the UI shows in the Action column.
DIR_INCREASE = "⬆️ Increase"
DIR_DECREASE = "⬇️ Decrease"
DIR_HOLD = "⏸️ Hold"


@dataclass(frozen=True)
class QuickAction:
    """One actionable nudge for one product."""

    product: str
    direction: str     # DIR_INCREASE / DIR_DECREASE / DIR_HOLD
    adjust: str        # "Stock" / "Price" / "—"
    by: str            # "+30 units" / "to R17 (median)" / "—"
    reason: str        # one-liner
    priority: int      # 0 (info) — 100 (urgent)

    def as_row(self) -> dict[str, Any]:
        return {
            "Action": self.direction,
            "Product": self.product,
            "Adjust": self.adjust,
            "By": self.by,
            "Reason": self.reason,
            "Priority": self.priority,
        }


# ---------------------------------------------------------------------------
# Per-signal action builders
# ---------------------------------------------------------------------------


def _restock_action(s: _ProductSignal) -> QuickAction | None:
    """Stock-side action for one product. None if nothing to do."""
    if s.sold == 0:
        return None
    if s.stock == 0:
        qty = _round_order(max(int(s.sold * 1.5), 6))
        return QuickAction(
            product=s.name,
            direction=DIR_INCREASE,
            adjust="Stock",
            by=f"+{qty} units",
            reason=f"sold out after {s.sold} sold last week",
            priority=100,
        )
    if s.weeks_left < 1:
        qty = _round_order(max(int(s.sold * 1.4), 6))
        return QuickAction(
            product=s.name,
            direction=DIR_INCREASE,
            adjust="Stock",
            by=f"+{qty} units",
            reason=f"only {s.stock} left vs {s.sold} sold — under a week",
            priority=80,
        )
    if s.sell_through >= 0.5 and s.sold >= 6:
        qty = _round_order(max(int(s.sold * 1.2), 6))
        return QuickAction(
            product=s.name,
            direction=DIR_INCREASE,
            adjust="Stock",
            by=f"+{qty} units",
            reason=f"{int(s.sell_through * 100)}% sell-through — top up for the weekend",
            priority=60,
        )
    if s.weeks_left < 2:
        qty = _round_order(max(s.sold, 5))
        return QuickAction(
            product=s.name,
            direction=DIR_INCREASE,
            adjust="Stock",
            by=f"+{qty} units",
            reason="around a week and a half of cover — reorder soon",
            priority=40,
        )
    return None


def _price_action(s: _ProductSignal) -> QuickAction | None:
    """Pricing-side action for one product. Requires a benchmark."""
    if s.bench is None:
        return None
    lo, _hi = s.bench["price_range_rand"]
    median = s.bench["median_price_rand"]

    # Top mover priced below the median → lift it to median.
    if s.sold >= 5 and s.sell_through >= 0.5:
        return QuickAction(
            product=s.name,
            direction=DIR_INCREASE,
            adjust="Price",
            by=f"to R{median}",
            reason=f"top mover ({s.sold} sold); township median is R{median}",
            priority=55,
        )

    # Slow stock with no movement → discount to the low end.
    if s.stock > 0 and s.sell_through < 0.3 and s.sold >= 1:
        return QuickAction(
            product=s.name,
            direction=DIR_DECREASE,
            adjust="Price",
            by=f"to R{lo}",
            reason=f"{s.stock} on the shelf vs only {s.sold} sold — promo to clear",
            priority=35,
        )

    return None


def _hold_action(s: _ProductSignal) -> QuickAction:
    """Catch-all 'no change' row so every product appears in the table."""
    return QuickAction(
        product=s.name,
        direction=DIR_HOLD,
        adjust="—",
        by="—",
        reason="balanced; sell-through and cover both healthy",
        priority=10,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def quick_actions_df(
    stock_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    benchmarks: dict[str, Any],
) -> pd.DataFrame:
    """Return one row per (product, signal), sorted by priority desc.

    Each product can produce up to two rows (one Stock, one Price). If
    neither signal fires, a single Hold row is emitted so the product
    still appears in the table.
    """
    bench_index = benchmarks_by_name(benchmarks)
    signals = _build_signals(stock_df, sales_df, bench_index)

    actions: list[QuickAction] = []
    for s in signals:
        stock_action = _restock_action(s)
        price_action = _price_action(s)
        if stock_action is not None:
            actions.append(stock_action)
        if price_action is not None:
            actions.append(price_action)
        if stock_action is None and price_action is None:
            actions.append(_hold_action(s))

    actions.sort(key=lambda a: (-a.priority, a.product))

    if not actions:
        return pd.DataFrame(
            columns=["Action", "Product", "Adjust", "By", "Reason", "Priority"]
        )

    return pd.DataFrame([a.as_row() for a in actions])


def quick_actions_to_csv(df: pd.DataFrame) -> bytes:
    """CSV export of the actions table."""
    return df.to_csv(index=False).encode("utf-8")
