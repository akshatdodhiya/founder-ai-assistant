# Autonomous Engineering Workflow: Founder AI Assistant

This document defines the strict development protocol for building the Context Engine. The agent must strictly adhere to these phases to guarantee deterministic RAG retrieval, prevent context drift, and maintain architectural integrity.

## 📂 Core Living Documents
- `ARCHITECTURE.md`: The single source of truth for schemas, ingestion pipelines, and retrieval logic.
- `CONTEXT.md`: System state, verified assumptions, and active trade-offs.
- `AGENTS.md`: Operational boundaries and constraints for the AI agent.
- `docs/adr/`: Architecture Decision Records capturing pivots and structural changes.

---

## 🛠️ Execution Protocol

### Phase 1: Boundary Definition (`/grill-with-docs`)
Before implementing any module (e.g., Normalization, Vector Storage, Query Routing):
1. Query the developer to clarify edge cases and schema constraints.
2. Verify alignment with `ARCHITECTURE.md`.
3. Update `CONTEXT.md` with explicit module contracts.

### Phase 2: Test-Driven Specification (TDD Red)
1. Write isolated unit/integration tests (`tests/test_<module>.py`).
2. Execute `pytest` and verify the tests **fail** for the expected architectural reason.
3. Lock the test suite. The agent is strictly prohibited from altering tests to make them pass.

### Phase 3: Minimal Implementation (TDD Green)
1. Implement the minimal clean code required to satisfy the failing tests.
2. Enforce strict typing using Pydantic models. No untyped dictionaries across module boundaries.
3. Run `pytest` to confirm all assertions pass cleanly.

### Phase 4: Self-Audit (`/code-review`)
Before committing, the agent inspects its diff against:
- Architectural drift from `ARCHITECTURE.md`.
- Token efficiency and context window budgeting.
- Hardcoded secrets, unhandled API exceptions, and hallucinated packages.

### Phase 5: Atomic Verification & Checkpoint
1. Run full test suite: `pytest tests/`.
2. Stage and commit changes locally with conventional commits: `feat(...)`, `fix(...)`, `test(...)`.

---

## ⚠️ Architectural Pivots (`/pivot`)
If retrieval performance, API constraints, or schema edge cases demand a structural change:
1. Stop all code generation immediately.
2. Log an ADR in `docs/adr/NNN-<description>.md`.
3. Update `ARCHITECTURE.md` to reflect the new system design.
4. Refactor existing unit tests to reflect the new invariants before touching production code.