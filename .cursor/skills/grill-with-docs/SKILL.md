---
name: grill-with-docs
description: Interview the user relentlessly to sharpen a feature design, update domain vocabulary in CONTEXT.md.
disable-model-invocation: true
---

# Grill With Docs & Issue Creation

Use this skill to align with the human developer before writing code. You will sharpen project terminology, document constraints, and create a tracking issue on GitHub.

## Process

### 1. Relentless Interview
Interview the user about the requested feature until every ambiguity is resolved. Ask questions covering:
- **Core capability:** What exact outcome does the caller expect?
- **Domain language:** What specific terms describe these concepts? Challenge vague terms (e.g., "account" vs "user").
- **Boundaries & edge cases:** What happens on bad input, missing data, or rate limits?

### 2. Maintain CONTEXT.md
Read `CONTEXT.md` at the project root (create it if missing).
- Update the glossary with any newly agreed terms using the format:
  ```markdown
  **Term**: Definition in 1-2 sentences. _Avoid_: Synonyms to avoid.
  ```
- **STRICT RULE:** `CONTEXT.md` contains domain terms, invariants, and business rules ONLY. Do NOT include file paths, code snippets, or temporary implementation notes.