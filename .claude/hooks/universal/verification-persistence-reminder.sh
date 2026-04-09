#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# verification-persistence-reminder.sh — PostToolUseFailure hook for Bash.
# Reminds the agent not to give up when Bash commands fail during verification.
# Only fires in acceptEdits mode: every 3rd failure, at most once per 30 seconds.

input=$(cat)

# Only fire in acceptEdits mode (agent following a plan)
permission_mode=$(echo "$input" | jq -r '.permission_mode // empty')
[[ "$permission_mode" == "acceptEdits" ]] || exit 0

session_id=$(echo "$input" | jq -r '.session_id // empty')
agent_id=$(echo "$input" | jq -r '.agent_id // empty')
scope_key="${session_id}:${agent_id}"

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

# every 3rd failure AND at most once per 30 seconds
if ! hook_gate verification-persistence "$scope_key" every 3 cooldown 30; then
  exit 0
fi

# shellcheck source=../lib/reminder-messages.sh
source "${HOOKS_DIR}/lib/reminder-messages.sh"

jq -n --arg ctx "$(reminder_verification_persistence "$HOOK_GATE_FIRES")" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUseFailure",
      "additionalContext": $ctx
    }
  }'
