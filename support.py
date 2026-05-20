"""Support ticket system — create, list, update, and export tickets.

This is deliberately session-scoped (no DB) because Streamlit Community
Cloud has an ephemeral filesystem. The UI persists tickets via
``st.session_state``; the helpers here are pure functions over Python
lists of :class:`Ticket` so they can be tested without Streamlit.

Status workflow: ``open → in_progress → resolved``. ``cycle_status`` is
the small state machine that drives the "Update status" button — it
loops back to ``open`` after ``resolved`` so the owner can re-open a
ticket without manually resetting it.

A ticket carries:

* ``id`` — monotonically-increasing integer assigned by ``next_id()``
* ``created`` — server-assigned timestamp at creation
* ``subject`` — short title (required)
* ``description`` — free-form body
* ``category``, ``priority``, ``status`` — fixed enums
* ``locale`` — the language the user submitted in (informational)
* ``context`` — optional snapshot, e.g. the advice ID that prompted
  the report. Free-form dict so the UI can stash whatever it likes
  without coupling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

import pandas as pd


CATEGORIES = ("advice", "pricing", "delivery", "bug", "other")
PRIORITIES = ("low", "medium", "high")
STATUSES = ("open", "in_progress", "resolved")
_STATUS_CYCLE = {"open": "in_progress", "in_progress": "resolved", "resolved": "open"}


# ---------------------------------------------------------------------------
# Domain type
# ---------------------------------------------------------------------------


@dataclass
class Ticket:
    """One support ticket / problem report."""

    id: int
    subject: str
    description: str
    category: str            # one of CATEGORIES
    priority: str            # one of PRIORITIES
    status: str              # one of STATUSES
    locale: str              # language code at submission ("en", "zu", ...)
    created: datetime
    context: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def next_id(tickets: Iterable[Ticket]) -> int:
    """Smallest positive integer not already used as an ID.

    Using ``max(ids) + 1`` is intentionally avoided so that deleting a
    ticket doesn't leave permanent gaps that look weird in the UI when
    the list is small.
    """
    used = {t.id for t in tickets}
    candidate = 1
    while candidate in used:
        candidate += 1
    return candidate


def cycle_status(status: str) -> str:
    """Advance to the next status in the open → in_progress → resolved loop."""
    return _STATUS_CYCLE.get(status, "open")


def create_ticket(
    subject: str,
    description: str,
    category: str = "other",
    priority: str = "medium",
    locale: str = "en",
    context: dict[str, Any] | None = None,
    now: datetime | None = None,
    existing: Iterable[Ticket] | None = None,
) -> Ticket:
    """Build a new Ticket. Raises ``ValueError`` on bad input.

    ``existing`` is used only to derive a fresh ``id`` — the caller
    is responsible for appending the result to their list.
    """
    subject = (subject or "").strip()
    if not subject:
        raise ValueError("Subject is required.")
    if category not in CATEGORIES:
        category = "other"
    if priority not in PRIORITIES:
        priority = "medium"

    return Ticket(
        id=next_id(existing or []),
        subject=subject,
        description=(description or "").strip(),
        category=category,
        priority=priority,
        status="open",
        locale=locale or "en",
        created=now or datetime.now(),
        context=dict(context or {}),
    )


def update_status(
    tickets: list[Ticket], ticket_id: int, new_status: str | None = None
) -> list[Ticket]:
    """Return a copy of ``tickets`` with the targeted ticket's status updated.

    Pass ``new_status=None`` to advance via the status cycle. Unknown
    statuses are clamped to the next cycle position to keep the UI
    well-defined.
    """
    out: list[Ticket] = []
    for t in tickets:
        if t.id == ticket_id:
            target = new_status if new_status in STATUSES else cycle_status(t.status)
            out.append(
                Ticket(
                    id=t.id, subject=t.subject, description=t.description,
                    category=t.category, priority=t.priority, status=target,
                    locale=t.locale, created=t.created, context=dict(t.context),
                )
            )
        else:
            out.append(t)
    return out


def delete_ticket(tickets: list[Ticket], ticket_id: int) -> list[Ticket]:
    """Return a copy of ``tickets`` with the ticket of ``ticket_id`` removed."""
    return [t for t in tickets if t.id != ticket_id]


# ---------------------------------------------------------------------------
# DataFrame + CSV adapters for the UI
# ---------------------------------------------------------------------------


def tickets_to_df(tickets: Iterable[Ticket]) -> pd.DataFrame:
    """One row per ticket, ranked by priority (high → low) then creation time desc."""
    priority_order = {"high": 0, "medium": 1, "low": 2}
    rows = []
    for t in sorted(
        tickets,
        key=lambda x: (priority_order.get(x.priority, 99), -x.created.timestamp()),
    ):
        rows.append(
            {
                "ID": t.id,
                "Subject": t.subject,
                "Category": t.category,
                "Priority": t.priority,
                "Status": t.status,
                "Locale": t.locale,
                "Created": t.created.isoformat(timespec="seconds"),
                "Description": t.description,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "ID", "Subject", "Category", "Priority",
                "Status", "Locale", "Created", "Description",
            ]
        )
    return pd.DataFrame(rows)


def filter_by_status(
    tickets: Iterable[Ticket], status: str | None
) -> list[Ticket]:
    """Filter to a single status, or return all if ``status`` is None/empty."""
    if not status:
        return list(tickets)
    return [t for t in tickets if t.status == status]


def tickets_to_csv(tickets: Iterable[Ticket]) -> bytes:
    return tickets_to_df(tickets).to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Seed data — so the demo opens with a story
# ---------------------------------------------------------------------------


def default_tickets(now: datetime | None = None) -> list[Ticket]:
    """Three plausible prior tickets so the Help tab isn't empty at first load."""
    now = now or datetime.now()
    return [
        Ticket(
            id=1,
            subject="Niknaks median price feels low",
            description=(
                "The advisor suggests R7 for Niknaks 30g but in my area Pick n Pay sells for R8. "
                "Could the benchmark be wider?"
            ),
            category="pricing",
            priority="low",
            status="open",
            locale="en",
            created=now,
            context={},
        ),
        Ticket(
            id=2,
            subject="Add Albany bread to catalogue",
            description=(
                "Lots of customers ask for Albany over Sasko. Could you add it as a separate product?"
            ),
            category="other",
            priority="medium",
            status="in_progress",
            locale="en",
            created=now,
            context={},
        ),
        Ticket(
            id=3,
            subject="Sales log date didn't save",
            description="I edited a date in the sales log but it reverted on the next click.",
            category="bug",
            priority="high",
            status="resolved",
            locale="en",
            created=now,
            context={},
        ),
    ]
