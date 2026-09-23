#!/usr/bin/env bash
# traces-session-env.sh — Cursor sessionStart hook
#
# Injects TRACES_CURRENT_TRACE_ID and TRACES_CURRENT_AGENT into the agent
# environment so that `traces share` can deterministically identify the active
# session.
#
# Install:
#   1. Copy this file to .cursor/hooks/traces-session-env.sh
#   2. chmod +x .cursor/hooks/traces-session-env.sh
#   3. Create or merge into .cursor/hooks.json:
#      {
#        "version": 1,
#        "hooks": {
#          "sessionStart": [{
#            "command": ".cursor/hooks/traces-session-env.sh",
#            "timeout": 5
#          }]
#        }
#      }

set -euo pipefail

# Read the hook event JSON from stdin
INPUT=$(cat)

# Extract session_id / conversation_id from the JSON payload
SESSION_ID=$(echo "$INPUT" | grep -o '"session_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')

if [ -z "${SESSION_ID:-}" ]; then
  SESSION_ID=$(echo "$INPUT" | grep -o '"conversation_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"conversation_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
fi

# Output env vars for the agent session
# Cursor sessionStart hooks can return { "env": { ... } } to inject env vars
if [ -n "${SESSION_ID:-}" ]; then
  echo "{\"env\":{\"TRACES_CURRENT_TRACE_ID\":\"${SESSION_ID}\",\"TRACES_CURRENT_AGENT\":\"cursor\"}}"
fi

exit 0
