"""Unit tests for the support / ticket module."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from support import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    SUPPORT_EMAIL,
    Ticket,
    build_bulk_mailto_url,
    build_mailto_url,
    create_ticket,
    cycle_status,
    default_tickets,
    delete_ticket,
    filter_by_status,
    next_id,
    tickets_to_csv,
    tickets_to_df,
    update_status,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_categories_priorities_statuses_define_the_workflow():
    assert "advice" in CATEGORIES and "bug" in CATEGORIES
    assert PRIORITIES == ("low", "medium", "high")
    assert STATUSES == ("open", "in_progress", "resolved")


# ---------------------------------------------------------------------------
# next_id
# ---------------------------------------------------------------------------


def test_next_id_is_one_on_empty_list():
    assert next_id([]) == 1


def test_next_id_avoids_used_ids():
    t = lambda i: Ticket(  # noqa: E731
        id=i, subject="x", description="", category="other",
        priority="low", status="open", locale="en", created=datetime.now(),
    )
    assert next_id([t(1), t(2), t(3)]) == 4


def test_next_id_fills_gaps():
    """Deleting ticket 2 from [1,2,3] should make 2 reusable."""
    t = lambda i: Ticket(  # noqa: E731
        id=i, subject="x", description="", category="other",
        priority="low", status="open", locale="en", created=datetime.now(),
    )
    assert next_id([t(1), t(3)]) == 2


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------


def test_create_ticket_fills_required_fields():
    t = create_ticket(
        subject="Help!",
        description="Something broke",
        category="bug",
        priority="high",
        locale="zu",
    )
    assert t.id == 1
    assert t.subject == "Help!"
    assert t.description == "Something broke"
    assert t.category == "bug"
    assert t.priority == "high"
    assert t.status == "open"
    assert t.locale == "zu"
    assert t.context == {}


def test_create_ticket_strips_whitespace_in_subject_and_description():
    t = create_ticket(subject="  trim me  ", description="\n body \n")
    assert t.subject == "trim me"
    assert t.description == "body"


def test_create_ticket_rejects_blank_subject():
    with pytest.raises(ValueError):
        create_ticket(subject="", description="x")
    with pytest.raises(ValueError):
        create_ticket(subject="   ", description="x")


def test_create_ticket_falls_back_to_safe_enums_for_unknown_values():
    t = create_ticket(subject="x", description="y", category="weird", priority="urgent")
    assert t.category == "other"
    assert t.priority == "medium"


def test_create_ticket_uses_next_id_from_existing():
    existing = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
        Ticket(
            id=2, subject="b", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    new = create_ticket(subject="c", description="", existing=existing)
    assert new.id == 3


def test_create_ticket_accepts_context_dict():
    t = create_ticket(
        subject="bad advice",
        description="...",
        context={"advice_id": "abc-123", "tab": "advice"},
    )
    assert t.context == {"advice_id": "abc-123", "tab": "advice"}


# ---------------------------------------------------------------------------
# cycle_status / update_status
# ---------------------------------------------------------------------------


def test_cycle_status_loops_through_workflow():
    assert cycle_status("open") == "in_progress"
    assert cycle_status("in_progress") == "resolved"
    assert cycle_status("resolved") == "open"


def test_cycle_status_unknown_returns_open():
    assert cycle_status("garbage") == "open"


def test_update_status_advances_when_no_target_given():
    tickets = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    out = update_status(tickets, 1)
    assert out[0].status == "in_progress"
    # Input untouched (functional-style)
    assert tickets[0].status == "open"


def test_update_status_jumps_to_explicit_target():
    tickets = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    out = update_status(tickets, 1, new_status="resolved")
    assert out[0].status == "resolved"


def test_update_status_ignores_unknown_id():
    tickets = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    out = update_status(tickets, ticket_id=999)
    assert out == tickets


# ---------------------------------------------------------------------------
# delete_ticket
# ---------------------------------------------------------------------------


def test_delete_ticket_removes_matching_id():
    tickets = [
        Ticket(
            id=1, subject="keep", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
        Ticket(
            id=2, subject="drop", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    out = delete_ticket(tickets, 2)
    assert [t.id for t in out] == [1]


def test_delete_ticket_returns_unchanged_when_id_missing():
    tickets = [
        Ticket(
            id=1, subject="x", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    out = delete_ticket(tickets, 999)
    assert out == tickets


# ---------------------------------------------------------------------------
# tickets_to_df
# ---------------------------------------------------------------------------


def test_tickets_to_df_ranks_by_priority_then_created_desc():
    older = datetime.now() - timedelta(hours=2)
    newer = datetime.now()
    tickets = [
        Ticket(
            id=1, subject="low one", description="", category="other",
            priority="low", status="open", locale="en", created=newer,
        ),
        Ticket(
            id=2, subject="high one", description="", category="bug",
            priority="high", status="open", locale="en", created=older,
        ),
        Ticket(
            id=3, subject="medium one", description="", category="advice",
            priority="medium", status="open", locale="en", created=newer,
        ),
    ]
    df = tickets_to_df(tickets)
    assert df.iloc[0]["Subject"] == "high one"
    assert df.iloc[1]["Subject"] == "medium one"
    assert df.iloc[2]["Subject"] == "low one"


def test_tickets_to_df_empty_returns_columns():
    df = tickets_to_df([])
    assert df.empty
    for col in ("ID", "Subject", "Category", "Priority", "Status", "Locale", "Created"):
        assert col in df.columns


# ---------------------------------------------------------------------------
# filter_by_status
# ---------------------------------------------------------------------------


def test_filter_by_status_returns_only_matching():
    tickets = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
        Ticket(
            id=2, subject="b", description="", category="other",
            priority="low", status="resolved", locale="en", created=datetime.now(),
        ),
    ]
    assert [t.id for t in filter_by_status(tickets, "open")] == [1]
    assert [t.id for t in filter_by_status(tickets, "resolved")] == [2]


def test_filter_by_status_none_or_empty_returns_all():
    tickets = [
        Ticket(
            id=1, subject="a", description="", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    assert filter_by_status(tickets, None) == tickets
    assert filter_by_status(tickets, "") == tickets


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def test_tickets_to_csv_has_header_and_one_row_per_ticket():
    tickets = [
        Ticket(
            id=1, subject="hello", description="world", category="other",
            priority="low", status="open", locale="en", created=datetime.now(),
        ),
    ]
    csv = tickets_to_csv(tickets).decode("utf-8")
    lines = csv.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("ID,Subject,Category")
    assert "hello" in lines[1]


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# mailto handoff
# ---------------------------------------------------------------------------


def _sample_ticket(**overrides) -> Ticket:
    defaults = dict(
        id=7,
        subject="Test ticket",
        description="Details go here",
        category="bug",
        priority="high",
        status="open",
        locale="en",
        created=datetime(2026, 5, 20, 12, 30, 0),
        context={"advice_id": "abc"},
    )
    defaults.update(overrides)
    return Ticket(**defaults)


def test_support_email_is_correct_recipient():
    assert SUPPORT_EMAIL == "dmartin@centennialschools.co.za"


def test_build_mailto_url_defaults_to_support_email():
    url = build_mailto_url(_sample_ticket())
    assert url.startswith("mailto:dmartin@centennialschools.co.za?")


def test_build_mailto_url_includes_ticket_id_and_subject():
    url = build_mailto_url(_sample_ticket(id=42, subject="Bread sold out"))
    # URL-encoded: spaces → %20
    assert "%5Bspazi%20shops%20%2342%5D%20Bread%20sold%20out" in url


def test_build_mailto_url_includes_description_and_context():
    url = build_mailto_url(_sample_ticket(description="Niknaks vanished"))
    assert "Niknaks%20vanished" in url
    assert "advice_id" in url  # JSON dump of context.


def test_build_mailto_url_accepts_custom_recipient():
    url = build_mailto_url(_sample_ticket(), recipient="other@example.com")
    assert url.startswith("mailto:other@example.com?")


def test_build_bulk_mailto_url_lists_every_ticket():
    tickets = [
        _sample_ticket(id=1, subject="One"),
        _sample_ticket(id=2, subject="Two"),
    ]
    url = build_bulk_mailto_url(tickets)
    # Each ticket id should appear in the body
    assert "%231" in url and "%232" in url
    # Subject mentions count
    assert "2%20tickets" in url


def test_build_bulk_mailto_url_handles_empty_list():
    url = build_bulk_mailto_url([])
    assert url.startswith("mailto:dmartin@centennialschools.co.za?")
    assert "0%20tickets" in url


def test_default_tickets_returns_three_with_workflow_coverage():
    now = datetime(2026, 5, 20, 12, 0, 0)
    tickets = default_tickets(now=now)
    assert len(tickets) == 3
    statuses = {t.status for t in tickets}
    # The demo should show all three states so the UI's status badges are obvious.
    assert statuses == {"open", "in_progress", "resolved"}
