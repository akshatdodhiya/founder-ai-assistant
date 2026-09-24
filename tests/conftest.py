import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from dotenv import dotenv_values

from src.storage import ContextStore

ROOT = Path(__file__).resolve().parents[1]


class DeterministicEmbeddingFunction:
    """Fixed-size embeddings so tests never download a model."""

    def name(self) -> str:
        return "deterministic"

    def __call__(self, input: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in input:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([byte / 255.0 for byte in digest[:32]])
        return vectors


@pytest.fixture
def embedding() -> DeterministicEmbeddingFunction:
    return DeterministicEmbeddingFunction()


@pytest.fixture
def store(tmp_path: Path, embedding: DeterministicEmbeddingFunction) -> Iterator[ContextStore]:
    context_store = ContextStore(tmp_path / "chroma_db", embedding_function=embedding)
    yield context_store
    context_store.close()


@pytest.fixture
def openrouter_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY") or dotenv_values(ROOT / ".env").get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set")
    return key
