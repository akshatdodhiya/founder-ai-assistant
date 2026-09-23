---
name: code-review
description: Audit changes against ARCHITECTURE.md, secret hygiene, and production standards.
---

# Code Review Protocol

Inspect all staged or recently modified files before committing.

## Review Axes

### 1. Secret Hygiene & Safety (CRITICAL)
- Confirm **NO raw API keys** (OpenRouter, OpenAI) exist in code, docstrings, or test files.
- Verify all API keys are strictly retrieved via `os.getenv("OPENROUTER_API_KEY")`.
- Verify `.env` is listed in `.gitignore`.

### 2. Architectural Alignment
- Compare the diff against `ARCHITECTURE.md`:
  - Does all ingested data normalize to the canonical `ContextItem` Pydantic model?
  - Are ChromaDB metadata fields restricted to flat primitive types (`str`, `int`, `float`, `bool`)?
  - Does the synthesizer enforce grounding with source citations and a fallback for empty context?

### 3. Engineering Quality
- Check for Fowler code smells: mysterious variable names, unhandled exceptions, and dead code.
- Ensure all public functions have clear Python type annotations.

## Output Format
- **PASS:** State that the module satisfies all invariants and is safe to commit.
- **FAIL:** List the exact blocker (e.g., "Leaked API key on line 14" or "Direct dict passed instead of ContextItem") and stop execution until fixed.