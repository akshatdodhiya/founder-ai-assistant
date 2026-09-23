# Root CLI launcher

**Date:** 2026-09-23
**Context:** ADR-0001 placed the interactive entrypoint at src/cli/main.py. Running that file as a script puts src/cli on sys.path, so imports like from src.models import ... fail. Adding the repo root to sys.path inside the module is a path hack.
**Decision:** A thin main.py at the repository root is the only documented entrypoint. python main.py starts the REPL. python main.py --test runs the three evaluation questions. The launcher calls src.cli.main. Interactive logic stays in src/cli/.
**Consequences:** This supersedes the entrypoint path in ADR-0001. Section 6 commands change to python main.py. No production CLI exists yet, so nothing in src/ needs rewriting.
