# System Context & Decisions

## Domain Terminology
- **Context Engine**: A centralized ingestion, indexing, and retrieval pipeline that grounds LLMs in temporal, cross-platform enterprise state.
- **Normalization**: Mapping polymorphic external data schemas into an immutable internal structure.
- **Metadata Pre-Filtering**: Restricting vector search spaces deterministically using structured temporal and categorical bounds before calculating cosine similarity.
- **Context Item**: One immutable normalized operational fact, either a meeting or an email. _Avoid_: document, chunk, row.
- **Source**: The system a Context Item came from. Allowed values are calendar and email. _Avoid_: connector, integration.
- **Requires Action**: Email-only flag meaning someone still owes the founder a reply or deliverable. _Avoid_: unread, urgent, blocked.
- **Reference Timestamp**: Fixed "now" for relative time. The evaluation anchor is 2026-09-23T09:00:00Z. _Avoid_: wall clock, datetime.now.
- **Day Window**: The UTC calendar day that contains the Reference Timestamp, from 2026-09-23T00:00:00Z through 2026-09-23T23:59:59Z inclusive. _Avoid_: today, local time, business hours.
- **Focus Set**: Calendar Context Items in the Day Window, union email Context Items in the Day Window whose Requires Action flag is true. Requires Action is never applied to calendar items. _Avoid_: action filter.
- **Normalization Error**: Rejection of a raw payload that cannot become a Context Item. Ingestion emits no partial item. _Avoid_: skip, best effort.

## Current System State
- **Phase**: Ingestion & Schema Definition.
- **Active Data Sources**: Mock Google Calendar (`calendar.json`), Mock Gmail (`emails.json`).
- **Target LLM Provider**: OpenRouter API.
- **Primary Evaluation Queries**:
  1. "What should I focus on today?"
  2. "What follow-ups am I missing?"
  3. "What customer issues are showing up repeatedly?"