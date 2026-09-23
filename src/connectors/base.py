import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import ContextItem


class NormalizationError(Exception):
    """Raised when a raw payload cannot become a Context Item."""


class BaseConnector(ABC):
    def __init__(self, path: Path) -> None:
        self.path = path

    @abstractmethod
    def fetch_records(self) -> list[ContextItem]:
        """Return every normalized record, or raise if any record is invalid."""


def load_records(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NormalizationError(f"cannot read payload from {path}") from exc
    if not isinstance(payload, list):
        raise NormalizationError("payload must be a list of records")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(payload):
        if not isinstance(record, dict):
            raise NormalizationError(f"record {index} must be an object")
        records.append(record)
    return records


def require_fields(record: dict[str, Any], fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise NormalizationError(f"missing required fields: {', '.join(missing)}")


def require_str(record: dict[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = record[field]
    if not isinstance(value, str) or (value == "" and not allow_empty):
        raise NormalizationError(f"{field} must be a non-empty string")
    return value


def parse_timestamp(raw: object) -> datetime:
    if not isinstance(raw, str) or raw == "":
        raise NormalizationError("timestamp must be an ISO 8601 string")
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NormalizationError("unparseable timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise NormalizationError("timestamp must be timezone-aware")
    return parsed
