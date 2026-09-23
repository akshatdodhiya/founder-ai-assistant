from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.connectors import MockCalendarConnector, MockGmailConnector, NormalizationError
from src.models import ContextItem

FIXTURES = Path(__file__).parent / "fixtures"


def test_calendar_record_normalizes_to_context_item() -> None:
    records = MockCalendarConnector(FIXTURES / "calendar_valid.json").fetch_records()

    assert records == [
        ContextItem(
            id="cal_001",
            source="calendar",
            timestamp=datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc),
            title="Sprint Planning",
            content="Meeting: Sprint Planning\nAttendees: Alex, Priya\nNotes: Scope the week",
            metadata={
                "source": "calendar",
                "timestamp_epoch": 1790175600,
                "category": "meeting",
            },
        )
    ]
    assert "requires_action" not in records[0].metadata


def test_email_record_normalizes_to_context_item() -> None:
    records = MockGmailConnector(FIXTURES / "email_valid.json").fetch_records()

    assert records == [
        ContextItem(
            id="email_102",
            source="email",
            timestamp=datetime(2026, 9, 23, 14, 30, tzinfo=timezone.utc),
            title="Need the deck",
            content="Subject: Need the deck\nFrom: Alex\n\nCan you send the investor deck today?",
            metadata={
                "source": "email",
                "timestamp_epoch": 1790173800,
                "sender": "Alex",
                "requires_action": True,
                "category": "investor",
            },
        )
    ]


def test_calendar_missing_start_time_raises() -> None:
    connector = MockCalendarConnector(FIXTURES / "calendar_missing_start.json")

    with pytest.raises(NormalizationError):
        connector.fetch_records()


def test_email_naive_date_raises() -> None:
    connector = MockGmailConnector(FIXTURES / "email_naive_date.json")

    with pytest.raises(NormalizationError):
        connector.fetch_records()
