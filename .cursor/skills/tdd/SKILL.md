---
name: tdd
description: Test-driven development execution protocol. Enforces strict Red-Green invariants without artificial wait states.
---

# Test-Driven Development (TDD) Protocol

TDD is a strict Red → Green → Refactor execution loop.

## Rules of the Loop

### 1. Red Phase (Failing Tests First)
- Write automated tests (`tests/test_<module>.py`) verifying expected behavior *before* writing implementation code.
- Run `pytest tests/test_<module>.py` in terminal and confirm the test **fails** due to missing capability, not an import or syntax error.

### 2. Green Phase (Minimal Implementation)
- Write the minimal code in `src/` necessary to make the failing test pass.
- Enforce strict typing via Pydantic schemas (`ContextItem`).
- Re-run `pytest tests/test_<module>.py` and confirm clean pass.

### 3. Refactor Phase (Clean Up)
- Run `/code-review` to inspect for code smells, hardcoded keys, or architectural drift.
- Clean up logic, verifying tests remain green after every edit.

---

## STRICT RULE: Test Modification Invariant

**The agent is strictly forbidden from modifying test assertions to force broken implementation code to pass.**

If a test fails during the Green phase, you MUST assume the implementation code in `src/` is incorrect. Fix the implementation.

**Legitimate Requirement Change Exception:**
If a test assertion is demonstrably outdated due to an updated requirement in `ARCHITECTURE.md`:
1. Explain to the user why the test is outdated.
2. Show the proposed diff.
3. Wait for explicit user confirmation before editing any test file.

---

## Test Boundaries & Anti-Patterns
- **Mock Only at System Edges:** Mock external file I/O or live API calls. NEVER mock internal database queries (ChromaDB), normalizer transforms, or query router logic. The context engine must execute real internal calculations.
- **No Tautological Tests:** Expected values must be explicit literals, not recomputed logic.