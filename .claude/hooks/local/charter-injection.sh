#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name // "SessionStart"')

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "${HOOKS_DIR}/../.." && pwd)"

# shellcheck source=../lib/charter-utils.sh
source "${HOOKS_DIR}/lib/charter-utils.sh"

charter_file=$(resolve_charter_path "$PROJECT_ROOT")
[[ -n "$charter_file" ]] || exit 0

content=$(<"$charter_file")
[[ -n "$content" ]] || exit 0

jq -n --arg ctx "$content" --arg event "$hook_event" \
  '{
    "hookSpecificOutput": {
      "hookEventName": $event,
      "additionalContext": $ctx
    }
  }'
