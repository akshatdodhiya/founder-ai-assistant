from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.models import ContextItem, SearchPlan


def test_context_item_is_frozen() -> None:
    item = ContextItem(
        id="cal_001",
        source="calendar",
        timestamp=datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc),
        title="Sprint Planning",
        content="Meeting: Sprint Planning\nAttendees: Alex\nNotes: Scope the week",
        metadata={"source": "calendar", "timestamp_epoch": 1758618000, "category": "meeting"},
    )

    with pytest.raises(ValidationError):
        item.title = "Changed"


def test_context_item_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ContextItem(
            id="cal_001",
            source="calendar",
            timestamp=datetime(2026, 9, 23, 9, 0),
            title="Sprint Planning",
            content="notes",
            metadata={"source": "calendar", "timestamp_epoch": 1, "category": "meeting"},
        )


def test_context_item_rejects_nested_metadata() -> None:
    with pytest.raises(ValidationError):
        ContextItem(
            id="cal_001",
            source="calendar",
            timestamp=datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc),
            title="Sprint Planning",
            content="notes",
            metadata={"attendees": ["Alex"]},
        )


def test_context_item_rejects_unknown_source() -> None:
    with pytest.raises(ValidationError):
        ContextItem(
            id="slack_001",
            source="slack",
            timestamp=datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc),
            title="Standup notes",
            content="notes",
            metadata={},
        )


def test_search_plan_defaults() -> None:
    plan = SearchPlan(semantic_query="customer issue")

    assert plan.source_filter is None
    assert plan.time_start_epoch is None
    assert plan.time_end_epoch is None
    assert plan.requires_action_only is False
