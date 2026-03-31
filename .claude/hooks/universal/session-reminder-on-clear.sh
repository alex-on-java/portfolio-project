#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# session-reminder-on-clear.sh — SessionStart hook.
# Reminds the agent about project principles after a "clear context" plan approval,
# where the agent starts with a fresh context and zero prior turns.

input=$(cat)

source_field=$(echo "$input" | jq -r '.source // empty')

# Only fire when the session started from a context clear, not on normal startup
[[ "$source_field" == "clear" ]] || exit 0

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=../lib/reminder-messages.sh
source "${HOOKS_DIR}/lib/reminder-messages.sh"

jq -n --arg ctx "$(reminder_north_star_principles)" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": $ctx
    }
  }'
