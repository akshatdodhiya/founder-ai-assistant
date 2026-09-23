# System Context & Decisions

## Domain Terminology
- **Context Engine**: A centralized ingestion, indexing, and retrieval pipeline that grounds LLMs in temporal, cross-platform enterprise state.
- **Normalization**: Mapping polymorphic external data schemas into an immutable internal structure.
- **Metadata Pre-Filtering**: Restricting vector search spaces deterministically using structured temporal and categorical bounds before calculating cosine similarity.
- **Context Item**: One immutable normalized operational fact, either a meeting or an email. _Avoid_: document, chunk, row.
- **Source**: The system a Context Item came from. Allowed values are calendar and email. _Avoid_: connector, integration.
- **Requires Action**: Email-only flag meaning someone still owes the founder a reply or deliverable. _Avoid_: unread, urgent, blocked.
- **Reference Timestamp**: The fixed "now" used to resolve relative time. Defaults to the evaluation anchor 2026-09-23T09:00:00Z and can be overridden by configuration, never by the wall clock implicitly. _Avoid_: wall clock, datetime.now.
- **Day Window**: The UTC calendar day that contains the Reference Timestamp, from 2026-09-23T00:00:00Z through 2026-09-23T23:59:59Z inclusive. _Avoid_: today, local time, business hours.
- **Week Window**: Monday 00:00:00 through Sunday 23:59:59 UTC of the week containing the Reference Timestamp. For the evaluation anchor that is 2026-09-21T00:00:00Z through 2026-09-27T23:59:59Z. _Avoid_: last 7 days, rolling week.
- **Next Meeting**: The calendar Context Item with the earliest start strictly after the Reference Timestamp. _Avoid_: upcoming meetings, most relevant meeting.
- **Focus Set**: Calendar Context Items in the Day Window, union email Context Items in the Day Window whose Requires Action flag is true. Requires Action is never applied to calendar items. _Avoid_: action filter.
- **Thread**: All emails that share one thread identifier. _Avoid_: conversation, chain.
- **Follow-up**: A Thread whose latest message, of any kind, requires action. It is represented by that latest message. A later message without Requires Action closes the Thread. _Avoid_: action-required email, unread email.
- **Repeated Issue**: A customer problem reported in two or more emails. Messages in the same Thread count separately. _Avoid_: duplicate, recurring ticket.
- **Search Plan**: One filtered retrieval over the context layer, ordered either by similarity (default) or by time (earliest first). A question resolves to one or more Search Plans. _Avoid_: query, filter.
- **Query Intent**: One of focus today, follow-ups, repeated customer issue, next meeting, or general. Chosen from the founder's question, never from an email. _Avoid_: prompt, JSON plan.
- **Time Window**: One of today, yesterday, tomorrow, this week, next meeting, or none. Bounds are computed from the Reference Timestamp, never by the classifier. _Avoid_: model date, epoch guess.
- **Normalization Error**: Rejection of a raw payload that cannot become a Context Item. Ingestion emits no partial item. _Avoid_: skip, best effort.
- **Storage Error**: A stored record that cannot become a Context Item. Retrieval emits no partial item. _Avoid_: skip, corrupt row.
- **Planning Failure**: The router could not produce valid Search Plans after one retry. The question is answered with an error, never with an unfiltered or ungrounded answer. _Avoid_: fallback search.

## Business Rules & Invariants
- Relative time phrases resolve only to these windows: today (Day Window), yesterday and tomorrow (the UTC days before and after the Day Window), this week (Week Window), and next meeting (Next Meeting). Any other phrase gets no time filter.
- When a question resolves to several Search Plans, their results are unioned, de-duplicated by Context Item id, and presented in chronological order.
- A Context Item read back from the context layer is identical to the one ingested, including its title and timestamp. The stored copy of title is not part of Context Item metadata after read. Retrieval always returns Context Items, never raw records.
- An empty ingest is a no-op.
- Unfiltered fetch returns every Context Item in chronological order.
- Follow-up detection looks at the latest message of every Thread, not only at messages flagged Requires Action.
- An empty event description or email body is valid. A missing field is a Normalization Error.
- Re-ingesting the same records never creates duplicates.
- Requires Action and category on an email come from the source record. Ingestion does not reclassify them.
- A low-confidence choice still uses the winning label.
- A follow-up window other than none keeps an open thread only when its latest message also falls inside that window.
- Similarity search uses the founder's question. A repeated customer issue searches for customer-problem wording instead of that raw question.
- Classification and synthesis share one provider credential.

## Current System State
- **Phase**: Query routing is implemented. Synthesis is next.
- **Active Data Sources**: Mock Google Calendar (`calendar.json`), Mock Gmail (`emails.json`).
- **Target Provider**: OpenRouter. Question classification uses a typed decision model. Synthesis uses a chat model. Both use the same credential. A failed classification is retried once before a Planning Failure.
- **Embeddings**: Local embedding model. Ingestion needs no API key; the first run downloads the model.
- **Primary Evaluation Queries**:
  1. "What should I focus on today?"
  2. "What follow-ups am I missing?"
  3. "What customer issues are showing up repeatedly?"
