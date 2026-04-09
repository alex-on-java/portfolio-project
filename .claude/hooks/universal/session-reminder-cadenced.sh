#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# session-reminder-cadenced.sh — UserPromptSubmit hook.
# Periodically reminds the agent about project principles.
# Fires on the 1st, 2nd user prompt, then every 2nd (4th, 6th, …).

input=$(cat)

session_id=$(echo "$input" | jq -r '.session_id // empty')
agent_id=$(echo "$input" | jq -r '.agent_id // empty')
scope_key="${session_id}:${agent_id}"

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

# burst_then_every 2 2 → fires at 0-indexed positions 0, 1, 3, 5, 7, 9 …
if ! hook_gate session-reminder "$scope_key" burst_then_every 2 2; then
  exit 0
fi

# shellcheck source=../lib/reminder-messages.sh
source "${HOOKS_DIR}/lib/reminder-messages.sh"

jq -n --arg ctx "$(reminder_north_star_principles)" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": $ctx
    }
  }'
