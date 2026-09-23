---
name: pivot
description: Handle core architectural design changes. Generates an ADR, updates ARCHITECTURE.md, and prevents context collisions.
disable-model-invocation: true
---

# Architecture Pivot

Use this skill when the user explicitly changes a core design decision, technology stack, or system-wide business rule that contradicts the current `ARCHITECTURE.md`.

## Process

### 1. Document the "Why" (The ADR)
1. Read the current `docs/adr/` directory to find the highest existing ADR number.
2. Create a new file in `docs/adr/` named `XXXX-brief-slug.md` (e.g., `0003-switch-to-postgis.md`).
3. Write the ADR using this exact format:
   ```markdown
   # {Short title of the decision}
   
   **Date:** {Current Date}
   **Context:** {Why is the current approach failing or changing?}
   **Decision:** {What is the new technology/pattern we are adopting?}
   **Consequences:** {What parts of the codebase will this break or require rewriting?}
   ```

### 2. Update the "What" (The Living Architecture)
1. Open `ARCHITECTURE.md` at the project root.
2. **STRICT RULE:** Locate the exact section that contains the outdated decision.
3. Completely rewrite that section to reflect the new decision. 
4. Delete any trace of the old, contradicting instruction so the LLM does not experience a context collision in future sessions.
5. Add a footnote to the rewritten section pointing to the new ADR (e.g., `*(See ADR-0003)*`).

### 3. Update the Roadmap (If Necessary)
If this pivot requires new immediate work (e.g., migrating existing databases), open `ROADMAP.md` and insert the new migration tasks at the top of the active phase with empty `[ ]` checkboxes.

### 4. Stage and Commit
Stage all changed markdown files and execute a local git commit:
`git commit -m "docs(architecture): pivot to [new concept] and record ADR-XXXX"`
