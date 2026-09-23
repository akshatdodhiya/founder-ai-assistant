# Typed storage round-trip

**Date:** 2026-09-23
**Context:** Section 4.2 returned search hits as untyped dicts of Chroma documents and metadata. WORKFLOW.md forbids untyped dictionaries across module boundaries, and Chroma stores only documents plus metadata, so title and the full timestamp were dropped. A search hit could not become the same Context Item that was ingested. The embedding model was also unspecified.
**Decision:** search() and fetch() return list[ContextItem]. At write time the storage layer copies title into Chroma metadata and rebuilds timestamp from timestamp_epoch on read. Connector metadata does not gain title. fetch(where, limit) returns filter-only results in chronological order with no vector ranking. Real runs use Chroma's default local embedding model (all-MiniLM-L6-v2). Tests inject a small deterministic embedding.
**Consequences:** The previous search() -> list[dict] contract is deleted. The synthesizer and router consume Context Items only. Re-ingesting the same ids uses upsert so duplicates are not created. The first real run downloads the embedding model; tests must not depend on that download.
