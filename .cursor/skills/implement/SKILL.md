---
name: implement
description: Execute local feature development using strict TDD, local code review, and local conventional commits.
disable-model-invocation: true
---

# Local Feature Implementer

Implement the feature described in the spec or target GitHub Issue.

## Execution Steps

1. **Verify Context:**
   Read `CONTEXT.md` to ensure domain terminology and constraints are understood.

2. **Execute TDD Red Phase:**
   Follow the `/tdd` skill rules. Write extensive integration tests for success paths, validation failures, and edge cases.
   - Run local tests using your testing tool (e.g., `pytest`).
   - Confirm tests **fail**.
   - **HALT & DISPLAY:** Show the failed test output to the human developer. Wait for confirmation before proceeding to code generation.

3. **Execute TDD Green Phase:**
   Write production implementation code to satisfy the locked tests.
   - Re-run local tests until all pass.
   - **STRICT RULE:** You are forbidden from altering test files to make them pass without explicit user permission (refer to `/tdd` Test Modification Protocol).

4. **Self Code Review:**
   Execute `/code-review` on the local diff (`git diff main...HEAD`). Fix any critical standards breaches or spec misalignments.

5. **Local Git Commit:**
   Stage modified files and execute a local commit using Conventional Commits syntax:
   ```bash
   git add .
   git commit -m "feat(scope): brief description of changes"
   ```

**CRITICAL GUARDRAIL:**
Do NOT execute `git push`. Do NOT use GitHub MCP to open a Pull Request. Stop execution and inform the user that local implementation and testing are complete and ready for review.
