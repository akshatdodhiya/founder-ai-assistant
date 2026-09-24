import json
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
                "thread_id": "thr_9",
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

    with pytest.raises(NormalizationError) as caught:
        connector.fetch_records()

    assert str(caught.value).count("email_naive_date.json") == 1


def test_calendar_unparseable_end_time_raises(tmp_path: Path) -> None:
    record = json.loads((FIXTURES / "calendar_valid.json").read_text(encoding="utf-8"))[0]
    record["end_time"] = "not a time"
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps([record]), encoding="utf-8")

    with pytest.raises(NormalizationError):
        MockCalendarConnector(path).fetch_records()


def test_error_names_file_and_failing_record(tmp_path: Path) -> None:
    good = json.loads((FIXTURES / "email_valid.json").read_text(encoding="utf-8"))[0]
    bad = {key: value for key, value in good.items() if key != "body"}
    bad["id"] = "902"
    path = tmp_path / "emails.json"
    path.write_text(json.dumps([good, bad]), encoding="utf-8")

    with pytest.raises(NormalizationError) as caught:
        MockGmailConnector(path).fetch_records()

    message = str(caught.value)
    assert message.count("emails.json") == 1
    assert "record 1" in message
    assert "902" in message
    assert "missing required fields: body" in message
