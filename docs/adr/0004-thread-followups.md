# Thread-aware follow-ups

**Date:** 2026-09-23
**Context:** Email payloads already contain thread_id, but normalized metadata omitted it. Follow-up detection was a single requires_action filter over every email, so three messages in one Acme thread counted as three follow-ups. A later reply that no longer requires action could not close the thread.
**Decision:** Email metadata includes thread_id. A follow-up is a thread whose latest message, of any kind, requires action, represented by that latest message. A later message without Requires Action closes the thread. Repeated issues still count every customer email, including messages in the same thread. The approved test change adds thread_id to the expected email metadata in tests/test_connectors.py.
**Consequences:** This supersedes ADR-0002's statement that follow-ups keep a single requires_action filter. Connector mapping and the follow-ups evaluation row change. Existing tests that omit thread_id fail until gmail.py writes it. Calendar metadata is unchanged.
