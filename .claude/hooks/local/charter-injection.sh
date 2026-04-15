#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name // "SessionStart"')
session_id=$(echo "$input" | jq -r '.session_id // empty')
agent_id=$(echo "$input" | jq -r '.agent_id // empty')
cwd=$(echo "$input" | jq -r '.cwd // empty')

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "${HOOKS_DIR}/../.." && pwd)"
effective_root="${cwd:-$PROJECT_ROOT}"

# shellcheck source=../lib/charter-utils.sh
source "${HOOKS_DIR}/lib/charter-utils.sh"
# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

charter_file=$(resolve_charter_path "$effective_root")
[[ -n "$charter_file" ]] || exit 0

content=$(<"$charter_file")
[[ -n "$content" ]] || exit 0

branch=$(git -C "$effective_root" branch --show-current 2>/dev/null) || exit 0
scope_key="${session_id}:${agent_id}:${branch}"
if ! hook_gate charter-injection "$scope_key" once; then
  exit 0
fi

jq -n --arg ctx "$content" --arg event "$hook_event" \
  '{
    "hookSpecificOutput": {
      "hookEventName": $event,
      "additionalContext": $ctx
    }
  }'
