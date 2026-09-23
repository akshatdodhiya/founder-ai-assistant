---
name: share-to-traces
description: Share the current coding session to Traces and return the share URL.
metadata:
  author: traces
  version: "1.2.0"
  cli-contract-version: "1"
  argument-hint: [optional trace id or source path]
---

# Share To Traces

Publish the active trace to Traces and return the URL.

## Triggers

- "share to traces"
- "publish this trace"
- "share this session"

## How Session Resolution Works

Use the current session ID when the runtime provides it. OpenCode's plugin
injects that ID into shell calls. OpenCode2 does not currently expose a stable
session ID to skills. Without an exact ID, list the current directory's traces
and select an explicit trace instead of relying on newest-session ordering. The
selected trace keeps its adapter's `opencode` or `opencode2` agent ID.

When the current session ID is visible in the context, pass it directly:

```bash
TRACES_CURRENT_TRACE_ID="<session-id>" traces share --cwd "$PWD" --agent auto --json
```

If the plugin provides the `traces_share` tool, prefer using that tool directly
instead of the bash command — it handles session context automatically.

If neither the plugin nor the tool is available, use the discovery flow below.

## Command

### When the OpenCode plugin is installed (recommended):

Use the `traces_share` tool directly — it handles everything.

If using bash instead:

```bash
traces share --cwd "$PWD" --agent auto --json
```

### Without the plugin:

```bash
# Step 1: List available traces
traces share --list --cwd "$PWD" --agent auto --json

# Step 2: Share the current runtime's trace by ID
traces share --trace-id <selected-id> --json
```

Use each candidate's `agentId` to distinguish `opencode` from `opencode2`.
If more than one candidate for the current runtime remains, show the candidates
and ask the user which one to share. Do not choose by recency. This fallback
applies to either runtime when no exact session ID or plugin tool is available.

## Visibility

Do NOT pass `--visibility` (or set the `visibility` tool parameter) unless the
user explicitly requests it. The CLI defaults to the correct visibility based
on the user's namespace type.

## Output Behavior

- Parse the JSON output and reply with the `sharedUrl`.
- Include which selector resolved the trace (`selectedBy`).
- On failure:
  - `AUTH_REQUIRED`: run `traces login`, then retry.
  - `TRACE_NOT_FOUND`: use `--list` to discover, then `--trace-id`.
  - `UPLOAD_FAILED`: check network, then retry.

## Historical sharing

Trigger: “share all my traces”.

When the user asks to share historical traces:

1. Run `traces share status --unshared --json` for the requested directory or roots.
2. If any relevant branch reports `No destination`, run `traces share config` and show the complete current map. Ask the user to choose each destination or `Don't share`; ask for confirmation before changing any rule, and preserve every existing rule when writing the full map with `traces share config --set`.
3. After a confirmed configuration change, rerun `traces share status --unshared --json` and do not upload until the scope is verified.
4. For each verified absolute filesystem root, run one command at a time: `traces share upload --dir <absolute-root> --json`.
5. Report deliberate `Don't share` opt-outs, every successful share URL, and every failure. A partial runtime failure may be retried; prior remote successes are skipped by default.

Safety rules:
- Never guess a namespace or silently change the active namespace.
- Never transfer a trace automatically; ask before any transfer or routing change.
- If upload preflight fails, stop and explain the issue; do not continue with another root.
- Keep the existing single-session sharing workflow unchanged for requests such as `share to traces` or `publish this trace`.
