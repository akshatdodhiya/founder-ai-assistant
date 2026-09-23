---
name: grill-with-docs
description: Challenge assumptions, resolve edge cases, and update domain terminology in CONTEXT.md before coding.
disable-model-invocation: true
---

# Architectural Alignment & Boundary Check

Use this skill before building a new subsystem (e.g., Normalization, ChromaDB Store, Query Router).

## Process

### 1. Architectural Cross-Examination
Interview the user on edge cases and failure modes:
- **Data Invariants:** What happens if a calendar event has no description or an email has no body?
- **Filtering Logic:** How should the system handle relative temporal queries ("today", "yesterday", "next Monday")?
- **Attribution & Hallucination:** How does the synthesizer behave when the vector search returns zero results?

### 2. Update CONTEXT.md
- Add any newly agreed domain terms, invariants, or edge-case decisions to `CONTEXT.md`.
- **STRICT RULE:** `CONTEXT.md` stores business domain rules, filter logic, and current project status only. Do not put scratchpad code or file paths here.