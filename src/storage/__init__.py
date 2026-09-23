from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from src.models import ContextItem

_COLLECTION_NAME = "founder_context"
_DEFAULT_PATH = Path("./chroma_db")


class StorageError(Exception):
    """Raised when a stored record cannot become a Context Item."""


class _QueryCompatibleEmbedding:
    """Adapts a callable embedder to Chroma's embed_query protocol."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def name(self) -> str:
        named = getattr(self._inner, "name", None)
        if callable(named):
            return str(named())
        return "injected"

    def is_legacy(self) -> bool:
        return True

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._inner(input)

    def embed_query(self, input: list[str]) -> list[list[float]]:
        embed_query = getattr(self._inner, "embed_query", None)
        if callable(embed_query):
            return embed_query(input)
        return self._inner(input)


def _normalize_where(where: dict[str, Any]) -> dict[str, Any]:
    """Split multi-operator field filters into Chroma $and clauses."""
    if "$and" in where or "$or" in where:
        return where
    clauses: list[dict[str, Any]] = []
    passthrough: dict[str, Any] = {}
    for key, value in where.items():
        if isinstance(value, dict) and len(value) > 1:
            clauses.extend({key: {operator: operand}} for operator, operand in value.items())
        else:
            passthrough[key] = value
    if not clauses:
        return where
    clauses.extend({key: value} for key, value in passthrough.items())
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


class ContextStore:
    def __init__(self, path: Path | None = None, embedding_function: Any | None = None) -> None:
        self.path = path or _DEFAULT_PATH
        self.path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.path))
        create_kwargs: dict[str, Any] = {
            "name": _COLLECTION_NAME,
            "metadata": {"hnsw:space": "cosine"},
        }
        if embedding_function is not None:
            create_kwargs["embedding_function"] = _QueryCompatibleEmbedding(embedding_function)
        self._collection: Collection = self._client.get_or_create_collection(**create_kwargs)

    def upsert(self, items: list[ContextItem]) -> None:
        if not items:
            return
        self._collection.upsert(
            ids=[item.id for item in items],
            documents=[item.content for item in items],
            metadatas=[{**item.metadata, "title": item.title} for item in items],
        )

    def search(self, query: str, n_results: int = 5, where: dict | None = None) -> list[ContextItem]:
        available = self._collection.count()
        if available == 0:
            return []
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(n_results, available),
            "include": ["documents", "metadatas"],
        }
        if where is not None:
            kwargs["where"] = _normalize_where(where)
        result = self._collection.query(**kwargs)
        ids = result["ids"][0] if result["ids"] else []
        documents = result["documents"][0] if result["documents"] else []
        metadatas = result["metadatas"][0] if result["metadatas"] else []
        return [
            self._to_context_item(item_id, document, metadata)
            for item_id, document, metadata in zip(ids, documents, metadatas, strict=True)
        ]

    def fetch(self, where: dict | None = None, limit: int | None = None) -> list[ContextItem]:
        if self._collection.count() == 0:
            return []
        kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if where is not None:
            kwargs["where"] = where
        result = self._collection.get(**kwargs)
        ids = result["ids"] or []
        documents = result["documents"] or []
        metadatas = result["metadatas"] or []
        items = [
            self._to_context_item(item_id, document, metadata)
            for item_id, document, metadata in zip(ids, documents, metadatas, strict=True)
        ]
        items.sort(key=lambda item: item.metadata["timestamp_epoch"])
        if limit is not None:
            return items[:limit]
        return items

    def count(self) -> int:
        return self._collection.count()

    def close(self) -> None:
        self._client = None  # type: ignore[assignment]
        self._collection = None  # type: ignore[assignment]

    def _to_context_item(self, item_id: str, document: str | None, metadata: dict[str, Any] | None) -> ContextItem:
        if document is None or metadata is None:
            raise StorageError(f"stored record {item_id!r} is missing document or metadata")
        stored = dict(metadata)
        title = stored.pop("title", None)
        if not isinstance(title, str) or title == "":
            raise StorageError(f"stored record {item_id!r} is missing title")
        epoch = stored.get("timestamp_epoch")
        if not isinstance(epoch, int):
            raise StorageError(f"stored record {item_id!r} is missing timestamp_epoch")
        source = stored.get("source")
        if source not in ("calendar", "email"):
            raise StorageError(f"stored record {item_id!r} has invalid source")
        return ContextItem(
            id=item_id,
            source=source,
            timestamp=datetime.fromtimestamp(epoch, tz=timezone.utc),
            title=title,
            content=document,
            metadata=stored,
        )
