# Focus-today retrieval is a union

**Date:** 2026-09-23
**Context:** The evaluation row for "What should I focus on today?" applied the day window and requires_action together as one AND filter, and expected both calendar and email hits. Calendar metadata has no requires_action field, so that AND drops every meeting.
**Decision:** The focus set is the union of two retrievals: calendar items whose timestamp falls in the UTC day window, and email items in that same window whose requires_action flag is true. requires_action is never applied to calendar items. SearchPlan is unchanged; the router issues two searches and unions the results.
**Consequences:** The router cannot answer this question with one Chroma where clause built from a single SearchPlan. Storage and synthesis are unaffected. Follow-ups and repeated customer issues keep their existing single-plan filters.
