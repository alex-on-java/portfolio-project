#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# before-writing-plan-skill-reminder.sh — UserPromptSubmit hook.
# Reminds the agent to invoke the `before-writing-a-plan` skill
# before writing the plan file.
# Fires on every other plan-mode user prompt (1st, 3rd, 5th, …).

input=$(cat)

permission_mode=$(echo "$input" | jq -r '.permission_mode // empty')
[[ "$permission_mode" != "plan" ]] && exit 0

session_id=$(echo "$input" | jq -r '.session_id // empty')

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/hook-gate.sh
source "${HOOKS_DIR}/lib/hook-gate.sh"

# every 2 → fires at 0-indexed positions 0, 2, 4, … (1st, 3rd, 5th plan-mode prompts)
if ! hook_gate before-writing-plan-reminder "$session_id" every 2; then
  exit 0
fi

jq -n '{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "Remember: before writing a single line of the plan to the file, invoke the `before-writing-a-plan` skill first."
  }
}'
