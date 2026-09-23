from pathlib import Path

from src.connectors.base import (
    BaseConnector,
    NormalizationError,
    load_records,
    parse_timestamp,
    require_fields,
    require_str,
)
from src.models import ContextItem

_CALENDAR_FIELDS = ("id", "summary", "start_time", "end_time", "attendees", "description")


class MockCalendarConnector(BaseConnector):
    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path or Path("data/calendar.json"))

    def fetch_records(self) -> list[ContextItem]:
        items: list[ContextItem] = []
        for record in load_records(self.path):
            require_fields(record, _CALENDAR_FIELDS)
            attendees = record["attendees"]
            if not isinstance(attendees, list) or not all(isinstance(name, str) for name in attendees):
                raise NormalizationError("attendees must be a list of names")
            timestamp = parse_timestamp(record["start_time"])
            summary = require_str(record, "summary")
            description = require_str(record, "description", allow_empty=True)
            raw_id = require_str(record, "id")
            items.append(
                ContextItem(
                    id=f"cal_{raw_id}",
                    source="calendar",
                    timestamp=timestamp,
                    title=summary,
                    content=(
                        f"Meeting: {summary}\n"
                        f"Attendees: {', '.join(attendees)}\n"
                        f"Notes: {description}"
                    ),
                    metadata={
                        "source": "calendar",
                        "timestamp_epoch": int(timestamp.timestamp()),
                        "category": "meeting",
                    },
                )
            )
        return items
