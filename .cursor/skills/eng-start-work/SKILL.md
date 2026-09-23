---
name: eng-start-work
description: Mandatory pre-work Git hygiene check and feature branch creation based on an issue number.
disable-model-invocation: true
---

# Engineer Start Work (Git Hygiene)

Prepare the local workspace before implementing any feature code.

## Process

1. **Verify Working Tree:**
   Run `git status`. If there are uncommitted changes or unstaged files, STOP immediately and inform the user. Do not proceed until the working tree is completely clean.

2. **Sync with Main:**
   Run the following commands sequentially:
   ```bash
   git checkout main
   git pull origin main
   ```
   If there are pull errors or merge conflicts, STOP and request human intervention.

3. **Create Feature Branch:**
   Extract the issue number passed by the user (e.g., `42`). Create and check out a new branch formatted as `feat/<issue_number>-<short-description>`:
   ```bash
   git checkout -b feat/42-driver-onboarding
   ```

4. **Confirm Readiness:**
   Confirm to the user that the workspace is synchronized with `origin/main` and ready on the feature branch.
