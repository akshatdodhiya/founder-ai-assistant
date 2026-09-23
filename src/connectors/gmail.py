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

_EMAIL_FIELDS = ("id", "thread_id", "sender", "subject", "date", "body", "requires_action", "category")


class MockGmailConnector(BaseConnector):
    def __init__(self, path: Path | None = None) -> None:
        super().__init__(path or Path("data/emails.json"))

    def fetch_records(self) -> list[ContextItem]:
        items: list[ContextItem] = []
        for record in load_records(self.path):
            require_fields(record, _EMAIL_FIELDS)
            requires_action = record["requires_action"]
            if not isinstance(requires_action, bool):
                raise NormalizationError("requires_action must be a boolean")
            timestamp = parse_timestamp(record["date"])
            subject = require_str(record, "subject")
            sender = require_str(record, "sender")
            body = require_str(record, "body", allow_empty=True)
            category = require_str(record, "category")
            raw_id = require_str(record, "id")
            require_str(record, "thread_id")
            items.append(
                ContextItem(
                    id=f"email_{raw_id}",
                    source="email",
                    timestamp=timestamp,
                    title=subject,
                    content=f"Subject: {subject}\nFrom: {sender}\n\n{body}",
                    metadata={
                        "source": "email",
                        "timestamp_epoch": int(timestamp.timestamp()),
                        "sender": sender,
                        "requires_action": requires_action,
                        "category": category,
                    },
                )
            )
        return items
