#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

input=$(cat)

file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
[[ -z "$file_path" ]] && exit 0

ext="${file_path##*.}"

case "$ext" in
  py|sh|java|js|ts|tsx|jsx|kts|tf|hcl|yaml|yml) ;;
  *) exit 0 ;;
esac

check_content=$(echo "$input" | jq -r '.tool_input.new_string // .tool_input.content // empty')
[[ -z "$check_content" ]] && exit 0

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/silencer-patterns.sh
source "${HOOKS_DIR}/lib/silencer-patterns.sh"

found_silencer=false

HASH_PAT="$(silencer_hash_pattern)"
SLASH_PAT="$(silencer_slash_pattern)"
BLOCK_PAT="$(silencer_block_pattern)"
ANNOT_PAT="$(silencer_annotation_pattern)"

case "$ext" in
  py|sh|yaml|yml)
    result=$(printf '%s\n' "$check_content" | grep -E "$HASH_PAT" || true)
    [[ -n "$result" ]] && found_silencer=true
    ;;
  tf|hcl)
    result=$(printf '%s\n' "$check_content" | grep -E "$HASH_PAT|$SLASH_PAT|$BLOCK_PAT" || true)
    [[ -n "$result" ]] && found_silencer=true
    ;;
  java|kts)
    result=$(printf '%s\n' "$check_content" | grep -E "$SLASH_PAT|$BLOCK_PAT|$ANNOT_PAT" || true)
    [[ -n "$result" ]] && found_silencer=true
    ;;
  js|ts|tsx|jsx)
    result=$(printf '%s\n' "$check_content" | grep -E "$SLASH_PAT|$BLOCK_PAT" || true)
    [[ -n "$result" ]] && found_silencer=true
    ;;
esac

[[ "$found_silencer" != true ]] && exit 0

# shellcheck source=../lib/reminder-messages.sh
source "${HOOKS_DIR}/lib/reminder-messages.sh"

jq -n --arg ctx "$(reminder_linter_silencers)" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": $ctx
  }
}'
