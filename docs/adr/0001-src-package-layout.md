# Package modules under src

**Date:** 2026-09-23
**Context:** AGENTS.md requires package isolation across connectors, models, storage, engine, and cli. ARCHITECTURE.md section 2 placed those responsibilities in flat modules under src/ (models.py, connectors.py, storage.py, router.py, synthesizer.py, main.py), while sections 4.3 and 4.4 already placed the router and synthesizer under src/engine/. The two layouts cannot both be canonical.
**Decision:** All runtime code lives in packages under src/: src/models/, src/connectors/, src/storage/, src/engine/, and src/cli/. The interactive entrypoint is src/cli/main.py.
**Consequences:** Import paths and the CLI command change before any implementation exists, so no production code needs rewriting. Later slices must add modules inside those packages rather than as new flat files under src/.
