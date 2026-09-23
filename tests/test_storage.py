import hashlib
from datetime import datetime, timezone
from pathlib import Path

import chromadb
import pytest

from src.models import ContextItem
from src.storage import ContextStore, StorageError

DAY_START_EPOCH = 1790121600
DAY_END_EPOCH = 1790207999


class DeterministicEmbeddingFunction:
    """Fixed-size embeddings so tests never download a model."""

    def name(self) -> str:
        return "deterministic"

    def __call__(self, input: list[str]) -> list[list[float]]:
        embeddings: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            embeddings.append([byte / 255.0 for byte in digest[:32]])
        return embeddings


def _meeting(item_id: str, title: str, when: datetime, epoch: int) -> ContextItem:
    return ContextItem(
        id=item_id,
        source="calendar",
        timestamp=when,
        title=title,
        content=f"Meeting: {title}\nAttendees: Alex\nNotes: notes",
        metadata={"source": "calendar", "timestamp_epoch": epoch, "category": "meeting"},
    )


def _email(
    item_id: str,
    title: str,
    when: datetime,
    epoch: int,
    *,
    requires_action: bool,
    sender: str = "Alex",
    thread_id: str = "thr_9",
    category: str = "investor",
) -> ContextItem:
    return ContextItem(
        id=item_id,
        source="email",
        timestamp=when,
        title=title,
        content=f"Subject: {title}\nFrom: {sender}\n\nbody",
        metadata={
            "source": "email",
            "timestamp_epoch": epoch,
            "sender": sender,
            "thread_id": thread_id,
            "requires_action": requires_action,
            "category": category,
        },
    )


CAL_TODAY = _meeting(
    "cal_001",
    "Sprint Planning",
    datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc),
    1790175600,
)
CAL_YESTERDAY = _meeting(
    "cal_002",
    "Design critique",
    datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc),
    1790089200,
)
EMAIL_TODAY = _email(
    "email_101",
    "Need the deck",
    datetime(2026, 9, 23, 14, 30, tzinfo=timezone.utc),
    1790173800,
    requires_action=True,
)
EMAIL_OLD = _email(
    "email_102",
    "FYI standup notes",
    datetime(2026, 9, 15, 11, 20, tzinfo=timezone.utc),
    1789471200,
    requires_action=False,
    sender="Priya Shah",
    thread_id="thr_standup",
    category="internal",
)
CORPUS = [CAL_TODAY, CAL_YESTERDAY, EMAIL_TODAY, EMAIL_OLD]


@pytest.fixture
def store(tmp_path: Path):
    path = tmp_path / "chroma_db"
    context_store = ContextStore(path, embedding_function=DeterministicEmbeddingFunction())
    yield context_store
    context_store.close()


def test_upsert_is_idempotent(store: ContextStore) -> None:
    store.upsert(CORPUS)
    assert store.count() == 4
    store.upsert(CORPUS)
    assert store.count() == 4


def test_empty_upsert_is_noop(store: ContextStore) -> None:
    store.upsert(CORPUS)
    store.upsert([])
    assert store.count() == 4


def test_search_filters_by_source_email(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.search("deck", n_results=5, where={"source": "email"})
    assert {item.id for item in results} == {"email_101", "email_102"}


def test_search_requires_action_excludes_calendar(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.search("deck", n_results=5, where={"requires_action": True})
    assert all(item.source == "email" for item in results)
    assert all(item.id != "cal_001" and item.id != "cal_002" for item in results)
    assert {item.id for item in results} == {"email_101"}


def test_search_epoch_range_excludes_outside_day_window(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.search(
        "meeting",
        n_results=5,
        where={"timestamp_epoch": {"$gte": DAY_START_EPOCH, "$lte": DAY_END_EPOCH}},
    )
    assert {item.id for item in results} == {"cal_001", "email_101"}


def test_search_round_trips_context_item_without_title_in_metadata(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.search(CAL_TODAY.content, n_results=1)
    assert results == [CAL_TODAY]
    assert "title" not in results[0].metadata


def test_fetch_earliest_calendar_meeting(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.fetch(where={"source": "calendar"}, limit=1)
    assert results == [CAL_YESTERDAY]


def test_fetch_unfiltered_returns_all_earliest_first(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.fetch(where=None)
    assert [item.id for item in results] == ["email_102", "cal_002", "email_101", "cal_001"]


def test_data_survives_reopen(store: ContextStore, tmp_path: Path) -> None:
    store.upsert(CORPUS)
    store.close()
    reopened = ContextStore(tmp_path / "chroma_db", embedding_function=DeterministicEmbeddingFunction())
    try:
        assert reopened.count() == 4
        fetched = reopened.fetch(where=None)
        assert {item.id for item in fetched} == {"cal_001", "cal_002", "email_101", "email_102"}
    finally:
        reopened.close()


def test_empty_collection_returns_empty_lists(store: ContextStore) -> None:
    assert store.search("anything") == []
    assert store.fetch() == []


def test_search_returns_fewer_than_n_results(store: ContextStore) -> None:
    store.upsert(CORPUS)
    results = store.search("deck", n_results=5, where={"source": "email"})
    assert len(results) == 2


def test_missing_title_raises_storage_error(store: ContextStore) -> None:
    store.upsert([CAL_TODAY])
    client = chromadb.PersistentClient(path=str(store.path))
    collection = client.get_collection("founder_context")
    existing = collection.get(ids=[CAL_TODAY.id], include=["metadatas", "documents", "embeddings"])
    metadata = dict(existing["metadatas"][0])
    metadata.pop("title", None)
    collection.delete(ids=[CAL_TODAY.id])
    collection.add(
        ids=[CAL_TODAY.id],
        documents=existing["documents"],
        metadatas=[metadata],
        embeddings=existing["embeddings"],
    )
    with pytest.raises(StorageError):
        store.fetch(where={"source": "calendar"})


def test_missing_timestamp_epoch_raises_storage_error(store: ContextStore) -> None:
    store.upsert([CAL_TODAY])
    client = chromadb.PersistentClient(path=str(store.path))
    collection = client.get_collection("founder_context")
    existing = collection.get(ids=[CAL_TODAY.id], include=["metadatas", "documents", "embeddings"])
    metadata = dict(existing["metadatas"][0])
    metadata.pop("timestamp_epoch", None)
    collection.delete(ids=[CAL_TODAY.id])
    collection.add(
        ids=[CAL_TODAY.id],
        documents=existing["documents"],
        metadatas=[metadata],
        embeddings=existing["embeddings"],
    )
    with pytest.raises(StorageError):
        store.search(CAL_TODAY.content, n_results=1)
