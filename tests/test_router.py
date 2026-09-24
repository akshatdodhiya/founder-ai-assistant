from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.connectors import MockCalendarConnector, MockGmailConnector
from src.engine.classifier import (
    Classification,
    ClassifierTransportError,
    JevClassifier,
    MissingAPIKeyError,
)
from src.engine.router import PlanningFailure, Router, build_where, compute_windows, compute_windows_from_env
from src.models import ContextItem, SearchPlan
from src.storage import ContextStore

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)
TODAY = (1790121600, 1790207999)
WEEK = (1789948800, 1790553599)
NEXT_START = 1790154001
REPEAT_QUERY = "customer issue bug error complaint"


class FakeClassifier:
    def __init__(self, results: list[Classification | Exception]) -> None:
        self._results = list(results)
        self.calls = 0

    def classify(self, query: str) -> Classification:
        self.calls += 1
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class RecordingStore:
    def __init__(self) -> None:
        self.calls = 0

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[ContextItem]:
        self.calls += 1
        return []

    def fetch(self, where: dict | None = None, limit: int | None = None) -> list[ContextItem]:
        self.calls += 1
        return []


def _load_eval(store: ContextStore) -> None:
    meetings = MockCalendarConnector(ROOT / "data" / "calendar.json").fetch_records()
    emails = MockGmailConnector(ROOT / "data" / "emails.json").fetch_records()
    store.upsert(meetings + emails)


def test_windows_for_anchor() -> None:
    windows = compute_windows(ANCHOR)

    assert windows["today"] == TODAY
    assert windows["yesterday"] == (1790035200, 1790121599)
    assert windows["tomorrow"] == (1790208000, 1790294399)
    assert windows["this_week"] == WEEK
    assert windows["next_meeting"] == (NEXT_START, None)


def test_reference_time_override_moves_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDER_REFERENCE_TIME", "2026-09-24T09:00:00Z")

    windows = compute_windows_from_env()

    assert windows["today"] == (1790208000, 1790294399)


def test_naive_reference_time_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FOUNDER_REFERENCE_TIME", "2026-09-24T09:00:00")

    with pytest.raises(ValueError):
        compute_windows_from_env()


def test_build_where_empty_is_none() -> None:
    plan = SearchPlan(semantic_query="anything")

    assert build_where(plan) is None


def test_build_where_source_only() -> None:
    plan = SearchPlan(semantic_query="anything", source_filter="email")

    assert build_where(plan) == {"source": "email"}


def test_build_where_combines_clauses() -> None:
    plan = SearchPlan(
        semantic_query="anything",
        source_filter="email",
        requires_action_only=True,
        time_start_epoch=TODAY[0],
        time_end_epoch=TODAY[1],
    )

    assert build_where(plan) == {
        "$and": [
            {"source": "email"},
            {"requires_action": True},
            {"timestamp_epoch": {"$gte": TODAY[0]}},
            {"timestamp_epoch": {"$lte": TODAY[1]}},
        ]
    }


def test_build_where_rejects_inverted_bounds() -> None:
    plan = SearchPlan(semantic_query="anything", time_start_epoch=20, time_end_epoch=10)

    with pytest.raises(ValueError):
        build_where(plan)


def test_focus_today_builds_two_plans() -> None:
    router = Router(FakeClassifier([Classification("focus_today", "none")]))

    plans = router.plan_query("What should I focus on today?", ANCHOR)

    assert plans == [
        SearchPlan(
            semantic_query="What should I focus on today?",
            source_filter="calendar",
            time_start_epoch=TODAY[0],
            time_end_epoch=TODAY[1],
            requires_action_only=False,
            order_by="time",
        ),
        SearchPlan(
            semantic_query="What should I focus on today?",
            source_filter="email",
            time_start_epoch=TODAY[0],
            time_end_epoch=TODAY[1],
            requires_action_only=True,
            order_by="time",
        ),
    ]


def test_follow_ups_without_window_have_no_time_bounds() -> None:
    router = Router(FakeClassifier([Classification("follow_ups", "none")]))

    plans = router.plan_query("What follow-ups am I missing?", ANCHOR)

    assert plans == [
        SearchPlan(
            semantic_query="What follow-ups am I missing?",
            source_filter="email",
            requires_action_only=True,
            order_by="time",
        )
    ]


def test_follow_ups_intersect_today() -> None:
    router = Router(FakeClassifier([Classification("follow_ups", "today")]))

    plans = router.plan_query("What follow-ups am I missing today?", ANCHOR)

    assert plans[0].time_start_epoch == TODAY[0]
    assert plans[0].time_end_epoch == TODAY[1]
    assert plans[0].requires_action_only is True


def test_repeated_customer_uses_fixed_wording() -> None:
    router = Router(FakeClassifier([Classification("repeated_customer", "none")]))

    plans = router.plan_query("What customer issues are showing up repeatedly?", ANCHOR)

    assert plans == [
        SearchPlan(
            semantic_query=REPEAT_QUERY,
            source_filter="email",
            order_by="similarity",
        )
    ]


def test_next_meeting_ignores_conflicting_window() -> None:
    router = Router(FakeClassifier([Classification("next_meeting", "today")]))

    plans = router.plan_query("What's my next meeting?", ANCHOR)

    assert plans == [
        SearchPlan(
            semantic_query="What's my next meeting?",
            source_filter="calendar",
            time_start_epoch=NEXT_START,
            time_end_epoch=None,
            requires_action_only=False,
            order_by="time",
        )
    ]


def test_classifier_retries_once_then_succeeds() -> None:
    classifier = FakeClassifier(
        [ClassifierTransportError("429"), Classification("general", "none")]
    )
    router = Router(classifier, sleep=lambda _seconds: None)

    plans = router.plan_query("status?", ANCHOR)

    assert classifier.calls == 2
    assert plans[0].semantic_query == "status?"
    assert plans[0].order_by == "similarity"
    assert plans[0].time_start_epoch is None


def test_two_classifier_failures_do_not_search() -> None:
    classifier = FakeClassifier(
        [ClassifierTransportError("429"), ClassifierTransportError("429")]
    )
    store = RecordingStore()
    router = Router(classifier, sleep=lambda _seconds: None)

    with pytest.raises(PlanningFailure):
        router.retrieve("status?", store, ANCHOR)

    assert store.calls == 0


def test_missing_api_key_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("src.engine.classifier.load_dotenv", lambda: False)

    with pytest.raises(MissingAPIKeyError):
        JevClassifier.from_env()


def test_retrieve_focus_set(store: ContextStore) -> None:
    _load_eval(store)
    router = Router(FakeClassifier([Classification("focus_today", "none")]))

    found = router.retrieve("What should I focus on today?", store, ANCHOR)

    assert [item.id for item in found] == ["email_205", "email_203", "cal_001", "cal_002", "cal_003"]


def test_retrieve_follow_ups(store: ContextStore) -> None:
    _load_eval(store)
    router = Router(FakeClassifier([Classification("follow_ups", "none")]))

    found = router.retrieve("What follow-ups am I missing?", store, ANCHOR)

    assert [item.id for item in found] == ["email_204", "email_205", "email_203"]


def test_retrieve_next_meeting(store: ContextStore) -> None:
    _load_eval(store)
    router = Router(FakeClassifier([Classification("next_meeting", "none")]))

    found = router.retrieve("What's my next meeting?", store, ANCHOR)

    assert [item.id for item in found] == ["cal_001"]


def test_closed_thread_is_excluded(store: ContextStore) -> None:
    older = ContextItem(
        id="email_old",
        source="email",
        timestamp=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc),
        title="Need a reply",
        content="Please reply",
        metadata={
            "source": "email",
            "timestamp_epoch": 1790006400,
            "sender": "Sam",
            "thread_id": "thr_closed",
            "requires_action": True,
            "category": "investor",
        },
    )
    newer = ContextItem(
        id="email_new",
        source="email",
        timestamp=datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc),
        title="All set",
        content="No further action",
        metadata={
            "source": "email",
            "timestamp_epoch": 1790179200,
            "sender": "Sam",
            "thread_id": "thr_closed",
            "requires_action": False,
            "category": "investor",
        },
    )
    store.upsert([older, newer])
    router = Router(FakeClassifier([Classification("follow_ups", "none")]))

    assert router.retrieve("What follow-ups am I missing?", store, ANCHOR) == []


FOCUS_QUERY = "What should I focus on today?"
FOCUS_IDS = ["email_205", "email_203", "cal_001", "cal_002", "cal_003"]


@pytest.mark.live
def test_live_jev_focus_today(tmp_path: Path, openrouter_key: str) -> None:
    context_store = ContextStore(tmp_path / "chroma")
    try:
        meetings = MockCalendarConnector(ROOT / "data" / "calendar.json").fetch_records()
        emails = MockGmailConnector(ROOT / "data" / "emails.json").fetch_records()
        context_store.upsert(meetings + emails)
        router = Router(JevClassifier(openrouter_key))
        plans = router.plan_query(FOCUS_QUERY, ANCHOR)
        found = router.collect(plans, context_store)
    finally:
        context_store.close()

    print(f"\nQuery: {FOCUS_QUERY}")
    for index, plan in enumerate(plans, start=1):
        print(f"Plan {index}")
        print(f"  semantic_query: {plan.semantic_query}")
        print(f"  source_filter: {plan.source_filter}")
        print(f"  time_start_epoch: {plan.time_start_epoch}")
        print(f"  time_end_epoch: {plan.time_end_epoch}")
        print(f"  requires_action_only: {plan.requires_action_only}")
        print(f"  order_by: {plan.order_by}")
    print("Retrieved:")
    for item in found:
        print(f"- {item.id}")
        print(f"  source: {item.source}")
        print(f"  title: {item.title}")
        print(f"  timestamp: {item.timestamp.isoformat()}")

    assert [item.id for item in found] == FOCUS_IDS
