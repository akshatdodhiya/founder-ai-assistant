---
name: tdd
description: Test-driven development reference & strict execution protocol. Use when building features or fixing bugs test-first.
---

# Test-Driven Development (TDD) Protocol

TDD is a strict Red → Green → Refactor execution loop. This document defines the rules of engagement for testing.

## Rules of the Loop

### 1. Red Phase (Failing Tests First)
- Write automated tests that verify expected behavior *before* writing implementation code.
- Run the test suite and confirm the new tests **fail**.
- Verify tests fail because the capability is missing, not due to syntax or import errors.

### 2. Green Phase (Minimal Implementation)
- Write the minimal amount of production code necessary to pass the failing tests.
- Do not add speculative capabilities or unrequested helper functions.

### 3. Refactor Phase (Clean Up)
- Once tests are green, run `/code-review` to inspect code standards and structure.
- Clean up messy logic, ensuring tests remain green after every edit.

---

## STRICT RULE: Test Modification Protocol

**The agent is strictly forbidden from modifying existing or approved test assertions to force broken implementation code to pass.**

If a test fails during the Green phase, you MUST assume your implementation code is incorrect. Fix the implementation code.

**Exception Handling:**
If you believe a test assertion is legitimately invalid due to a changed requirement:
1. **HALT execution immediately.**
2. Explain to the user precisely why the test assertion is outdated.
3. Show the exact diff you propose making to the test file.
4. **Wait for explicit user confirmation** before editing any test file.

---

## Test Architecture & Anti-Patterns

### Seams (Where Tests Live)
Test exclusively at public interfaces (API endpoints, public service methods). Never test private implementation details or internal helper state.

### Anti-Patterns to Avoid
- **Implementation-Coupled Tests:** Tests that break during refactoring even though public behavior did not change.
- **Tautological Tests:** Assertions that recompute expected values using the same logic as the code under test (e.g., `assert add(2, 3) == 2 + 3`). Expected values must be hardcoded known literals (e.g., `assert add(2, 3) == 5`).
- **Over-Mocking:** Mock **only** at system boundaries (external APIs, time/randomness, third-party infrastructure). Do NOT mock internal collaborators, domain models, or helper modules. Use in-memory test databases (SQLite) over database mocks whenever possible.
