from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContextItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique deterministic identifier (e.g., 'cal_001', 'email_102')")
    source: Literal["calendar", "email"] = Field(..., description="Originating data source")
    timestamp: datetime = Field(..., description="UTC ISO 8601 timestamp for temporal filtering")
    title: str = Field(..., description="Event summary or email subject")
    content: str = Field(..., description="Dense textual payload for vector embedding")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Flat primitives for metadata filtering (sender, attendees, category, requires_action)",
    )

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value

    @field_validator("metadata")
    @classmethod
    def metadata_values_must_be_primitives(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key, item in value.items():
            if isinstance(item, bool) or isinstance(item, (str, int, float)):
                continue
            raise ValueError(f"metadata[{key!r}] must be str, int, float, or bool")
        return value


class SearchPlan(BaseModel):
    semantic_query: str = Field(..., description="Refined semantic string for vector search")
    source_filter: Optional[Literal["calendar", "email"]] = Field(
        None, description="Source restriction if query specifies"
    )
    time_start_epoch: Optional[int] = Field(None, description="Unix epoch lower bound for filtering")
    time_end_epoch: Optional[int] = Field(None, description="Unix epoch upper bound for filtering")
    requires_action_only: bool = Field(
        False, description="Filter for unread/action-required emails or blockers"
    )
