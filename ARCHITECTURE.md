# System Architecture: Founder AI Assistant Context Engine

## 1. System Overview & Core Invariants

A local context engine designed to ingest disparate operational feeds (Google Calendar, Gmail), normalize them into a canonical representation, and perform metadata-aware semantic retrieval to answer founder operational questions.

### Core Requirements & Invariants

* **Multi-Source Ingestion**: Ingest data from at least 2 distinct operational sources (Google Calendar and Gmail).
* **Canonical Schema**: Standardize raw data into an immutable, unified Pydantic schema before storage.
* **Central Context Layer**: Persist vector embeddings and flat metadata in a local ChromaDB collection.
* **Grounded Retrieval Over Pure Tool Calling**: Answers must be derived strictly from stored context retrieved through vector and metadata queries rather than zero-shot LLM speculation or live API calls.
* **Decoupled Adapter Layer**: Connectors simulate production API payloads (`calendar.json`, `emails.json`), allowing real Google APIs or integration platforms like Composio/Nango to be substituted without modifying storage or synthesis logic.
* **OpenRouter LLM Integration**: Route requests and synthesize final answers using the provided OpenRouter API endpoint.

---

## 2. Directory Layout & Module Responsibilities

*(See ADR-0001)*

```text
founder-assistant/
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
│   └── test_router.py
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

All raw records must validate against `ContextItem` before entering the storage layer.

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
        description="Flat primitives for metadata filtering (sender, attendees, category, requires_action)"
    )

class SearchPlan(BaseModel):
    semantic_query: str = Field(..., description="Refined semantic string for vector search")
    source_filter: Optional[Literal["calendar", "email"]] = Field(None, description="Source restriction if query specifies")
    time_start_epoch: Optional[int] = Field(None, description="Unix epoch lower bound for filtering")
    time_end_epoch: Optional[int] = Field(None, description="Unix epoch upper bound for filtering")
    requires_action_only: bool = Field(False, description="Filter for unread/action-required emails or blockers")
```

---

## 4. Subsystem Pipelines

### 4.1 Ingestion & Normalization (`src/connectors/`)

* `BaseConnector(ABC)`: Defines abstract method `fetch_records() -> list[ContextItem]`.
* Constructors accept a file path. The default paths are `data/calendar.json` and `data/emails.json`.
* A raw record that is missing a required field, or whose timestamp is missing, unparseable, or naive, raises `NormalizationError`. `fetch_records()` emits no partial item.
* `MockCalendarConnector(BaseConnector)`:

  * Parses calendar payloads (fields: `id`, `summary`, `start_time`, `end_time`, `attendees`, `description`). `attendees` is a list of names.
  * Normalizes to `ContextItem`:

    * `id`: `f"cal_{raw['id']}"`
    * `source`: `"calendar"`
    * `timestamp`: Parsed timezone-aware ISO datetime from `start_time`
    * `title`: `raw['summary']`
    * `content`: `f"Meeting: {raw['summary']}\nAttendees: {', '.join(raw['attendees'])}\nNotes: {raw['description']}"`
    * `metadata`: `{"source": "calendar", "timestamp_epoch": int(ts.timestamp()), "category": "meeting"}` — no `requires_action` key
* `MockGmailConnector(BaseConnector)`:

  * Parses email payloads (fields: `id`, `thread_id`, `sender`, `subject`, `date`, `body`, `requires_action`, `category`).
  * Normalizes to `ContextItem`:

    * `id`: `f"email_{raw['id']}"`
    * `source`: `"email"`
    * `timestamp`: Parsed timezone-aware ISO datetime from `date`
    * `title`: `raw['subject']`
    * `content`: `f"Subject: {raw['subject']}\nFrom: {raw['sender']}\n\n{raw['body']}"`
    * `metadata`: `{"source": "email", "timestamp_epoch": int(ts.timestamp()), "sender": raw['sender'], "requires_action": bool(raw['requires_action']), "category": raw['category']}`

### 4.2 Central Context Storage (`src/storage/`)

* **Engine**: ChromaDB PersistentClient targeting `./chroma_db`.
* **Collection**: `founder_context` with cosine similarity distance.
* **ChromaDB Ingestion Constraint**: Metadata dictionaries in Chroma must contain only flat primitive types (`str`, `int`, `float`, `bool`).
* **Index Attributes**:

  * `ids`: `[item.id for item in items]`
  * `documents`: `[item.content for item in items]`
  * `metadatas`: `[item.metadata for item in items]`
* **Query Method**: `search(query: str, n_results: int = 5, where: dict = None) -> list[dict]`.

### 4.3 Query Router (`src/engine/router.py`)

Direct vector search fails on relative temporal queries ("today", "this week"). The Router runs an LLM call via OpenRouter (`openai/gpt-4o-mini`) using JSON mode to extract structured filters:

1. **Inputs**: Raw user query + Reference timestamp (Current anchor: `2026-09-23T09:00:00Z`).
2. **Output**: A populated `SearchPlan` schema.
3. **Filter Construction**:

* If `source_filter` is present, generate `{"source": plan.source_filter}`.
* If `requires_action_only` is true, add `{"requires_action": True}`.
* If epoch timestamps are provided, apply Chroma `$gte` and `$lte` operators.
* Combine multiple filters using Chroma's `$and` clause.

### 4.4 Synthesis Layer (`src/engine/synthesizer.py`)

1. Ingests retrieved `ContextItem` chunks alongside the founder's original prompt.
2. Calls OpenRouter LLM using an executive Chief-of-Staff system prompt.
3. **Grounding Invariant**: Answers must be strictly grounded in provided context chunks.
4. **Attribution**: Every claim must cite the source (e.g., `[Calendar: Sprint Planning]` or `[Email from Alex (Tech Lead)]`).
5. **No Hallucination Fallback**: If retrieved context is insufficient, state: *"I do not have sufficient context in your calendar or emails to answer this."*

---

## 5. Primary Test Scenarios & Expected Routing

*(See ADR-0002)*

The implementation must deterministically answer the core founder workflows. The reference timestamp is `2026-09-23T09:00:00Z`. The day window is that UTC calendar day, from `2026-09-23T00:00:00Z` through `2026-09-23T23:59:59Z` inclusive.

| Test Question                                         | Router Intent & Filters                                                                                                      | Primary Source          | Output Focus                                                 |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| **"What should I focus on today?"**                   | Union of two retrievals: calendar items inside the day window, and email items inside the day window with `requires_action: true`. `requires_action` is never applied to calendar items. | Calendar + Emails       | Chronological meeting priorities + urgent email deliverables |
| **"What follow-ups am I missing?"**                   | Source: `email`, `requires_action: True`                           | Emails                  | Pending external requests from investors and clients         |
| **"What customer issues are showing up repeatedly?"** | Semantic: `"customer issue bug error complaint"`, Source: `email`  | Support/Feedback Emails | Clustered recurring bugs with client citations               |

---

## 6. CLI & Automated Execution Interface (`src/cli/main.py`)

*(See ADR-0001)*

* **Interactive REPL**: `python src/cli/main.py` provides an interactive shell for open-ended queries.
* **Automated Test Mode**: `python src/cli/main.py --test` runs ingestion, executes the 3 required evaluation questions, and prints grounded responses.
