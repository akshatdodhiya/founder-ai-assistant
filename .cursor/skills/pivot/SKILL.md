---
name: pivot
description: Handle core architectural changes. Generates an ADR, updates ARCHITECTURE.md, and prevents context collisions.
disable-model-invocation: true
---

# Architecture Pivot

Use this skill when an underlying technical requirement or database invariant changes mid-build.

## Process

### 1. Document the Decision (ADR)
1. Check `docs/adr/` for the next sequential number (e.g., `docs/adr/0001-chroma-epoch-timestamps.md`).
2. Write the ADR documenting the **Context**, **Decision**, and **Consequences**.

### 2. Update ARCHITECTURE.md
1. Open `ARCHITECTURE.md`[cite: 1].
2. Overwrite the outdated section completely to prevent AI context collisions[cite: 1].
3. Link the updated section to the new ADR.

### 3. Commit the Documentation
Stage and commit the changes immediately:
```bash
git add docs/adr/ ARCHITECTURE.md
git commit -m "docs(architecture): pivot to <new decision> and record ADR-XXXX"
```