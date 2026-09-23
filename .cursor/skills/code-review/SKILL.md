---
description: Two-axis review of changes against repository standards and the originating specification.
---

# Code Review Protocol

Execute a two-axis review of the local git diff relative to the `main` branch.

## Review Axes

### Axis 1: Standards & Code Smells
Review the diff against `CODING_STANDARDS.md` (if present) and flag Fowler code smells:
- **Mysterious Name:** Functions, variables, or types with uninformative names.
- **Duplicated Code:** Identical or near-identical logic in multiple places.
- **Feature Envy:** A function reaching extensively into another object's data.
- **Primitive Obsession:** Using raw strings/integers instead of domain objects.
- **Shotgun Surgery:** A single logical change forcing scattered edits across many files.
- **Speculative Generality:** Abstractions, hooks, or parameters added for hypothetical future needs.

### Axis 2: Specification Alignment
Check local implementation against the originating spec or GitHub Issue:
- **Missing Requirements:** Specs asked for but not implemented.
- **Scope Creep:** Behavior added that was not requested in the spec/issue.
- **Incorrect Logic:** Features implemented in ways that violate `CONTEXT.md` rules.

### Axis 3: Architectural Drift Check
Compare the git diff (`git diff main...HEAD`) directly against `ARCHITECTURE.md`:
- Did this code introduce a new library, database pattern, or API structure not documented in `ARCHITECTURE.md`?
- Did this code alter a core business rule defined in `ARCHITECTURE.md`?

**Action:** If architectural drift is detected and no corresponding ADR exists in `docs/adr/`, mark the review as **FAILED**. Inform the user that they must execute `/pivot` to update the architecture before this branch can be shipped.

## Output Format
Present findings clearly split into `## Standards` and `## Spec` sections. Categorize findings as **Critical** (must fix before commit) or **Warning** (judgement call).
