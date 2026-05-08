#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

target="${SHOULD_USE_ENTER_WORKTREE:-}"
[[ -n "$target" ]] || exit 0

input=$(cat)
hook_event=$(echo "$input" | jq -r '.hook_event_name // "SessionStart"')
cwd=$(echo "$input" | jq -r '.cwd // empty')

canon() { [[ -e "$1" ]] && realpath "$1" 2>/dev/null || echo "$1"; }
if [[ -n "$cwd" ]] && [[ "$(canon "$cwd")" == "$(canon "$target")" ]]; then
  exit 0
fi

message="Please call 'ToolSearch select:EnterWorktree' and then use 'EnterWorktree' tool with path '${target}' as **the very first step**."

jq -n --arg ctx "$message" --arg event "$hook_event" \
  '{
    "hookSpecificOutput": {
      "hookEventName": $event,
      "additionalContext": $ctx
    }
  }'
