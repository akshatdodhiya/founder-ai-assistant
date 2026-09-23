# System Context & Decisions

## Domain Terminology
- **Context Engine**: A centralized ingestion, indexing, and retrieval pipeline that grounds LLMs in temporal, cross-platform enterprise state.
- **Normalization**: Mapping polymorphic external data schemas into an immutable internal structure.
- **Metadata Pre-Filtering**: Restricting vector search spaces deterministically using structured temporal and categorical bounds before calculating cosine similarity.

## Current System State
- **Phase**: Ingestion & Schema Definition.
- **Active Data Sources**: Mock Google Calendar (`calendar.json`), Mock Gmail (`emails.json`).
- **Target LLM Provider**: OpenRouter API.
- **Primary Evaluation Queries**:
  1. "What should I focus on today?"
  2. "What follow-ups am I missing?"
  3. "What customer issues are showing up repeatedly?"