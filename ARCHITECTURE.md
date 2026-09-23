# System Architecture: Founder AI Assistant Context Engine

## 1. System Overview & Core Invariants

A local context engine designed to ingest disparate operational feeds (Google Calendar, Gmail), normalize them into a canonical representation, and perform metadata-aware semantic retrieval to answer founder operational questions.

### Core Requirements & Invariants

* **Multi-Source Ingestion**: Ingest data from at least 2 distinct operational sources (Google Calendar and Gmail).
* **Canonical Schema**: Standardize raw data into an immutable, unified Pydantic schema before storage.
* **Central Context Layer**: Persist vector embeddings and flat metadata in a local ChromaDB collection.
* **Typed Round-Trip**: Every record leaving storage is a `ContextItem` identical to the one ingested, including title and timestamp. *(See ADR-0003)*
* **Grounded Retrieval Over Pure Tool Calling**: Answers must be derived strictly from stored context retrieved through vector and metadata queries rather than zero-shot LLM speculation or live API calls.
* **Decoupled Adapter Layer**: Connectors simulate production API payloads (`calendar.json`, `emails.json`), allowing real Google APIs or integration platforms like Composio/Nango to be substituted without modifying storage or synthesis logic.
* **OpenRouter LLM Integration**: Route requests and synthesize final answers using the provided OpenRouter API endpoint. Router failures retry once, then raise a Planning Failure. They never fall back to an unfiltered search. *(See ADR-0005)*

---

## 2. Directory Layout & Module Responsibilities

*(See ADR-0001, ADR-0006)*

```text
founder-assistant/
├── main.py                 # Thin launcher: python main.py / python main.py --test
├── data/
│   ├── calendar.json       # Mock Google Calendar event payloads
│   └── emails.json         # Mock Gmail message payloads
├── docs/
│   └── adr/                # Architecture decision records
├── src/
│   ├── __init__.py
│   ├── models/             # Canonical Pydantic schemas (ContextItem, SearchPlan)
│   ├── connectors/         # BaseConnector interface and source adapters
│   ├── storage/            # Persistent ChromaDB client and metadata indexer
│   ├── engine/
│   │   ├── router.py       # Query decomposition and OpenRouter search planning
│   │   └── synthesizer.py  # Grounded response generation with source citations
│   └── cli/
│       └── main.py         # Interactive CLI loop and evaluation test harness
├── tests/
│   ├── test_models.py
│   ├── test_connectors.py
│   ├── test_storage.py
│   ├── test_router.py
│   ├── test_synthesizer.py
│   └── test_cli.py
├── .env.example
├── requirements.txt
├── README.md
├── ASSESSMENT.md
├── ARCHITECTURE.md
├── WORKFLOW.md
└── AGENTS.md
```

---

## 3. Canonical Schemas (`src/models/`)

*(See ADR-0005)*

All raw records must validate against `ContextItem` before entering the storage layer. A question resolves to one or more `SearchPlan` objects.

```python
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

class ContextItem(BaseModel):
    id: str = Field(..., description="Unique deterministic identifier (e.g., 'cal_001', 'email_102')")
    source: Literal["calendar", "email"] = Field(..., description="Originating data source")
    timestamp: datetime = Field(..., description="UTC ISO 8601 timestamp for temporal filtering")
    title: str = Field(..., description="Event summary or email subject")
    content: str = Field(..., description="Dense textual payload for vector embedding")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Flat primitives for metadata filtering (sender, thread_id, category, requires_action)"
    )

class SearchPlan(BaseModel):
    semantic_query: str = Field(..., description="Refined semantic string for vector search")
    source_filter: Optional[Literal["calendar", "email"]] = Field(None, description="Source restriction if query specifies")
    time_start_epoch: Optional[int] = Field(None, description="Unix epoch lower bound for filtering")
    time_end_epoch: Optional[int] = Field(None, description="Unix epoch upper bound for filtering")
    requires_action_only: bool = Field(False, description="Filter for action-required emails")
    order_by: Literal["similarity", "time"] = Field(
        "similarity",
        description="similarity uses vector search; time uses filter-only fetch, earliest first",
    )
```

`ContextItem` is frozen. `timestamp` must be timezone-aware. Metadata values are limited to `str`, `int`, `float`, and `bool`.

---

## 4. Subsystem Pipelines

### 4.1 Ingestion & Normalization (`src/connectors/`)

*(See ADR-0004)*

* `BaseConnector(ABC)`: Defines abstract method `fetch_records() -> list[ContextItem]`.
* Constructors accept a file path. The default paths are `data/calendar.json` and `data/emails.json`.
* A raw record that is missing a required field, or whose timestamp is missing, unparseable, or naive, raises `NormalizationError`. `fetch_records()` emits no partial item.
* An empty event description or email body is valid. Only a missing field is a `NormalizationError`.
* `MockCalendarConnector(BaseConnector)`:

  * Parses calendar payloads (fields: `id`, `summary`, `start_time`, `end_time`, `attendees`, `description`). `attendees` is a list of names.
  * Normalizes to `ContextItem`:

    * `id`: `f"cal_{raw['id']}"`
    * `source`: `"calendar"`
    * `timestamp`: Parsed timezone-aware ISO datetime from `start_time`
    * `title`: `raw['summary']`
    * `content`: `f"Meeting: {raw['summary']}\nAttendees: {', '.join(raw['attendees'])}\nNotes: {raw['description']}"`
    * `metadata`: `{"source": "calendar", "timestamp_epoch": int(ts.timestamp()), "category": "meeting"}` — no `requires_action` key, no `title` key
* `MockGmailConnector(BaseConnector)`:

  * Parses email payloads (fields: `id`, `thread_id`, `sender`, `subject`, `date`, `body`, `requires_action`, `category`).
  * Normalizes to `ContextItem`:

    * `id`: `f"email_{raw['id']}"`
    * `source`: `"email"`
    * `timestamp`: Parsed timezone-aware ISO datetime from `date`
    * `title`: `raw['subject']`
    * `content`: `f"Subject: {raw['subject']}\nFrom: {raw['sender']}\n\n{raw['body']}"`
    * `metadata`: `{"source": "email", "timestamp_epoch": int(ts.timestamp()), "sender": raw['sender'], "thread_id": raw['thread_id'], "requires_action": bool(raw['requires_action']), "category": raw['category']}` — no `title` key

### 4.2 Central Context Storage (`src/storage/`)

*(See ADR-0003)*

* **Engine**: ChromaDB PersistentClient targeting `./chroma_db`.
* **Collection**: `founder_context` with cosine similarity distance.
* **Embeddings**: Chroma's default local model (`all-MiniLM-L6-v2`) in real runs. The embedding function is injectable so tests use a small deterministic embedding and never download a model.
* **ChromaDB Ingestion Constraint**: Metadata dictionaries in Chroma must contain only flat primitive types (`str`, `int`, `float`, `bool`).
* **Write path (`upsert(items: list[ContextItem]) -> None`)**:

  * `ids`: `[item.id for item in items]`
  * `documents`: `[item.content for item in items]`
  * `metadatas`: connector metadata plus `title` copied from `item.title`. Connector metadata does not itself contain `title`.
* **Read path**: Rebuild `ContextItem` from `id`, document (`content`), stored metadata, `title` from stored metadata, and `timestamp` from `timestamp_epoch` (UTC). The rebuilt item equals the ingested item.
* **Query methods**:

  * `search(query: str, n_results: int = 5, where: dict | None = None) -> list[ContextItem]`: cosine ranking.
  * `fetch(where: dict | None = None, limit: int | None = None) -> list[ContextItem]`: filter only, earliest timestamp first. Used for time-ordered plans and for reading whole threads.
  * `count() -> int`
* **Filter construction helpers used by the router**:

  * If `source_filter` is present, generate `{"source": plan.source_filter}`.
  * If `requires_action_only` is true, add `{"requires_action": True}`.
  * If epoch timestamps are provided, apply Chroma `$gte` and `$lte` on `timestamp_epoch`.
  * Combine two or more clauses with `$and`. A single clause is a plain dict. An empty filter is `None`, not `{}`.

### 4.3 Query Router (`src/engine/router.py`)

*(See ADR-0002, ADR-0005)*

Direct vector search fails on relative temporal queries ("today", "this week", "next meeting"). The Router runs an LLM call via OpenRouter (`openai/gpt-4o-mini`) using JSON mode to extract one or more structured plans.

1. **Inputs**: Raw user query + Reference Timestamp. Default `2026-09-23T09:00:00Z`, overridden by `FOUNDER_REFERENCE_TIME`. Never implicit wall clock.
2. **Window math (in code, not by the model)**:

   * today: UTC day containing the Reference Timestamp
   * yesterday / tomorrow: the UTC days before and after that day
   * this week: Monday 00:00:00 through Sunday 23:59:59 UTC of the week containing the Reference Timestamp
   * next meeting: calendar items with `timestamp` strictly after the Reference Timestamp
   * any other phrase: no time filter
3. **Output**: `list[SearchPlan]`. The model selects among the windows above using the exact epoch values supplied in the prompt. It never computes dates itself.
4. **Execution (`retrieve`)**:

   * `order_by="similarity"` calls `search`.
   * `order_by="time"` calls `fetch` (next meeting uses `source=calendar`, `time_start_epoch` exclusive of the Reference Timestamp, `limit=1`).
   * Union results, drop duplicate ids, sort remaining items by timestamp.
5. **Follow-ups**: After retrieving action-required emails, `fetch` every message in those threads. Keep a thread only when its latest message, of any kind, requires action. Represent the thread by that latest message. *(See ADR-0004)*
6. **Failure**: Timeout, HTTP 429, or invalid JSON is retried once. A second failure raises a Planning Failure. No unfiltered search is issued.

### 4.4 Synthesis Layer (`src/engine/synthesizer.py`)

1. Ingests retrieved `ContextItem` chunks alongside the founder's original prompt.
2. Calls OpenRouter LLM using an executive Chief-of-Staff system prompt.
3. **Grounding Invariant**: Answers must be strictly grounded in provided context chunks.
4. **Attribution**: Every claim must cite the source (e.g., `[Calendar: Sprint Planning]` or `[Email from Alex (Tech Lead)]`).
5. **No Hallucination Fallback**: If retrieved context is insufficient, state: *"I do not have sufficient context in your calendar or emails to answer this."*

---

## 5. Primary Test Scenarios & Expected Routing

*(See ADR-0002, ADR-0004, ADR-0005)*

The implementation must deterministically answer the core founder workflows. The default Reference Timestamp is `2026-09-23T09:00:00Z`. The day window is that UTC calendar day, from `2026-09-23T00:00:00Z` (`1790121600`) through `2026-09-23T23:59:59Z` (`1790207999`) inclusive. The week window is Monday `2026-09-21T00:00:00Z` (`1789948800`) through Sunday `2026-09-27T23:59:59Z` (`1790553599`).

| Test Question                                         | Router Intent & Filters                                                                                                      | Primary Source          | Output Focus                                                 |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| **"What should I focus on today?"**                   | Two SearchPlans unioned: calendar items inside the day window, and email items inside the day window with `requires_action: true`. `requires_action` is never applied to calendar items. | Calendar + Emails       | Chronological meeting priorities + urgent email deliverables |
| **"What follow-ups am I missing?"**                   | Emails with `requires_action: true`, then keep only threads whose latest message (of any kind) requires action. Represent each open thread by that latest message. | Emails                  | Pending external requests from investors and clients         |
| **"What customer issues are showing up repeatedly?"** | Semantic: `"customer issue bug error complaint"`, Source: `email`. Messages in the same thread count separately. | Support/Feedback Emails | Clustered recurring bugs with client citations               |
| **"What's my next meeting?"**                         | One time-ordered plan: calendar items with timestamp strictly after the Reference Timestamp, `order_by="time"`, limit 1. | Calendar                | The earliest upcoming meeting                                |

---

## 6. CLI & Automated Execution Interface (`main.py`)

*(See ADR-0006)*

* **Interactive REPL**: `python main.py` provides an interactive shell for open-ended queries. The file is a thin launcher that calls `src.cli.main`.
* **Automated Test Mode**: `python main.py --test` runs ingestion, executes the 3 required evaluation questions, and prints grounded responses.
* **Reference Timestamp**: Read `FOUNDER_REFERENCE_TIME` if set; otherwise use `2026-09-23T09:00:00Z`.
