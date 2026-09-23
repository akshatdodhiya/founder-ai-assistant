---
name: implement
description: Autonomously execute a vertical slice using strict TDD, static audit, and atomic git commit.
disable-model-invocation: true
---

# Feature Implementation Flow

Implement the module specified by the user adhering strictly to `ARCHITECTURE.md`.

## Autonomous Execution Steps

1. **Verify Invariants:**
   Read `ARCHITECTURE.md` and `CONTEXT.md` to confirm module contracts, schemas, and inputs.

2. **Execute TDD Red Phase:**
   - Write integration/unit tests in `tests/test_<module>.py`.
   - Execute `pytest tests/test_<module>.py` via terminal.
   - Confirm tests **fail** as expected.

3. **Execute TDD Green Phase:**
   - Write the minimal production code in `src/` to satisfy the failing test.
   - Execute `pytest tests/test_<module>.py` via terminal until all tests pass.
   - **LOCKOUT RULE:** Do not touch the test file during this step.

4. **Self Code Review:**
   - Execute `/code-review` against the modified files.
   - Ensure zero raw API keys are committed and all data crosses boundaries via `ContextItem`.

5. **Atomic Commit:**
   - Stage modified files and execute a local git commit on `main`:
     example:
     ```bash
     git add src/ tests/
     git commit -m "feat(<module>): implement <concise description of feature>"
     ```
   - Commit all those files that were related to the feature.  
   - Notify the user that the module is complete, verified by tests, and committed.