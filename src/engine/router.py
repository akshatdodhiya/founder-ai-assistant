import os
import time
from collections.abc import Callable
from datetime import date, datetime, timezone

from src.engine.classifier import Classification, ClassifierTransportError
from src.models import ContextItem, SearchPlan
from src.storage import ContextStore

_ANCHOR = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)
_REPEAT_QUERY = "customer issue bug error complaint"
_INTENTS = {"focus_today", "follow_ups", "repeated_customer", "next_meeting", "general"}
_WINDOWS = {"today", "yesterday", "tomorrow", "this_week", "next_meeting", "none"}


class PlanningFailure(Exception):
    """The router could not produce valid Search Plans."""


def resolve_reference_time() -> datetime:
    raw = os.getenv("FOUNDER_REFERENCE_TIME")
    if raw is None or raw == "":
        return _ANCHOR
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("FOUNDER_REFERENCE_TIME must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("FOUNDER_REFERENCE_TIME must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def compute_windows(reference: datetime) -> dict[str, tuple[int, int | None]]:
    if reference.tzinfo is None or reference.utcoffset() is None:
        raise ValueError("reference timestamp must be timezone-aware")
    current = reference.astimezone(timezone.utc)
    today = current.date()
    monday = today.fromordinal(today.toordinal() - today.weekday())
    sunday = monday.fromordinal(monday.toordinal() + 6)
    return {
        "today": _day_bounds(today),
        "yesterday": _day_bounds(today.fromordinal(today.toordinal() - 1)),
        "tomorrow": _day_bounds(today.fromordinal(today.toordinal() + 1)),
        "this_week": (_day_bounds(monday)[0], _day_bounds(sunday)[1]),
        "next_meeting": (int(current.timestamp()) + 1, None),
    }


def compute_windows_from_env() -> dict[str, tuple[int, int | None]]:
    return compute_windows(resolve_reference_time())


def build_where(plan: SearchPlan) -> dict | None:
    if (
        plan.time_start_epoch is not None
        and plan.time_end_epoch is not None
        and plan.time_start_epoch > plan.time_end_epoch
    ):
        raise ValueError("time_start_epoch is after time_end_epoch")
    clauses: list[dict] = []
    if plan.source_filter is not None:
        clauses.append({"source": plan.source_filter})
    if plan.requires_action_only:
        clauses.append({"requires_action": True})
    if plan.time_start_epoch is not None:
        clauses.append({"timestamp_epoch": {"$gte": plan.time_start_epoch}})
    if plan.time_end_epoch is not None:
        clauses.append({"timestamp_epoch": {"$lte": plan.time_end_epoch}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class Router:
    def __init__(self, classifier: object, sleep: Callable[[float], None] | None = None) -> None:
        self.classifier = classifier
        self._sleep = sleep or time.sleep

    def plan_query(self, query: str, reference: datetime) -> list[SearchPlan]:
        failure: ClassifierTransportError | None = None
        for attempt in (1, 2):
            try:
                classification = self.classifier.classify(query)  # type: ignore[attr-defined]
            except ClassifierTransportError as exc:
                failure = exc
                if attempt == 1:
                    self._sleep(1)
                    continue
                raise PlanningFailure("classifier failed after one retry") from exc
            return _plans(classification, query, reference)
        raise PlanningFailure("classifier failed after one retry") from failure

    def retrieve(self, query: str, store: ContextStore, reference: datetime) -> list[ContextItem]:
        found: list[ContextItem] = []
        seen: set[str] = set()
        for plan in self.plan_query(query, reference):
            hits = _run_plan(store, plan)
            if plan.requires_action_only and plan.source_filter == "email":
                hits = _open_threads(store, hits, plan)
            for hit in hits:
                if hit.id in seen:
                    continue
                seen.add(hit.id)
                found.append(hit)
        found.sort(key=lambda item: item.metadata["timestamp_epoch"])
        return found


def _plans(classification: Classification, query: str, reference: datetime) -> list[SearchPlan]:
    if classification.intent not in _INTENTS or classification.window not in _WINDOWS:
        raise PlanningFailure("classifier returned an unknown label")
    windows = compute_windows(reference)
    if classification.intent == "focus_today":
        start, end = windows["today"]
        return [
            _plan(query, "calendar", start, end, action=False, order_by="time"),
            _plan(query, "email", start, end, action=True, order_by="time"),
        ]
    if classification.intent == "next_meeting":
        start, end = windows["next_meeting"]
        return [_plan(query, "calendar", start, end, action=False, order_by="time")]
    start, end = _selected_window(classification.window, windows)
    if classification.intent == "follow_ups":
        return [_plan(query, "email", start, end, action=True, order_by="time")]
    if classification.intent == "repeated_customer":
        return [_plan(_REPEAT_QUERY, "email", start, end, action=False, order_by="similarity")]
    return [_plan(query, None, start, end, action=False, order_by="similarity")]


def _selected_window(
    window: str, windows: dict[str, tuple[int, int | None]]
) -> tuple[int | None, int | None]:
    if window == "none":
        return None, None
    return windows[window]


def _plan(
    semantic_query: str,
    source: str | None,
    start: int | None,
    end: int | None,
    *,
    action: bool,
    order_by: str,
) -> SearchPlan:
    return SearchPlan(
        semantic_query=semantic_query,
        source_filter=source,  # type: ignore[arg-type]
        time_start_epoch=start,
        time_end_epoch=end,
        requires_action_only=action,
        order_by=order_by,  # type: ignore[arg-type]
    )


def _run_plan(store: ContextStore, plan: SearchPlan) -> list[ContextItem]:
    where = build_where(plan)
    if plan.order_by == "time":
        limit = 1 if _is_next_meeting(plan) else None
        return store.fetch(where=where, limit=limit)
    return store.search(plan.semantic_query, n_results=5, where=where)


def _is_next_meeting(plan: SearchPlan) -> bool:
    return plan.source_filter == "calendar" and plan.time_end_epoch is None and plan.time_start_epoch is not None


def _open_threads(store: ContextStore, hits: list[ContextItem], plan: SearchPlan) -> list[ContextItem]:
    kept: list[ContextItem] = []
    seen: set[str] = set()
    for hit in hits:
        thread_id = hit.metadata.get("thread_id")
        if not isinstance(thread_id, str) or thread_id in seen:
            continue
        seen.add(thread_id)
        messages = store.fetch(where={"thread_id": thread_id})
        if not messages:
            continue
        latest = max(messages, key=lambda item: item.metadata["timestamp_epoch"])
        if latest.metadata.get("requires_action") is not True:
            continue
        if not _inside(latest, plan):
            continue
        kept.append(latest)
    return kept


def _inside(item: ContextItem, plan: SearchPlan) -> bool:
    epoch = item.metadata["timestamp_epoch"]
    if not isinstance(epoch, int):
        return False
    if plan.time_start_epoch is not None and epoch < plan.time_start_epoch:
        return False
    if plan.time_end_epoch is not None and epoch > plan.time_end_epoch:
        return False
    return True


def _day_bounds(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = datetime(day.year, day.month, day.day, 23, 59, 59, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())
