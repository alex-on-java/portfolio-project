#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# PreToolUse hook for Edit/Write: fires when the agent writes comments to code
# files, nudging toward the "Comments Fossilize Context" working principle.
#
# Input:  JSON on stdin (PreToolUse payload)
# Output: exit 0 always (non-blocking advisory). Emits hookSpecificOutput when
#         comments are detected.

input=$(cat)

file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
[[ -z "$file_path" ]] && exit 0

ext="${file_path##*.}"

case "$ext" in
  py|sh|java|js|ts|tsx|jsx|kts|tf|hcl|yaml|yml) ;;
  *) exit 0 ;;
esac

# Edit uses new_string; Write uses content
check_content=$(echo "$input" | jq -r '.tool_input.new_string // .tool_input.content // empty')
[[ -z "$check_content" ]] && exit 0

# Patterns catch both start-of-line and inline comments (e.g. `x = 1  # note`).
# [[:space:]] after # also excludes #! and #fff. [[:space:]] before // excludes https://.
HASH_PAT='(^|[[:space:]])#[[:space:]]'
SLASH_PAT='(^|[[:space:]])//'

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/silencer-patterns.sh
source "${HOOKS_DIR}/lib/silencer-patterns.sh"

HASH_DIRECTIVE='#[[:space:]]*(coding[=:]|shellcheck[[:space:]]+(source|shell|enable)=)'
SLASH_DIRECTIVE='///[[:space:]]*<reference'
BLOCK_DIRECTIVE='\*[[:space:]]*webpack'

HASH_PRAGMA="$(silencer_hash_pattern)|${HASH_DIRECTIVE}"
SLASH_PRAGMA="$(silencer_slash_pattern)|${SLASH_DIRECTIVE}"
BLOCK_PRAGMA="$(silencer_block_pattern)|${BLOCK_DIRECTIVE}"

found_comment=false

case "$ext" in
  py|sh|yaml|yml)
    result=$(printf '%s\n' "$check_content" | grep -E "$HASH_PAT" | grep -vE "$HASH_PRAGMA" || true)
    [[ -n "$result" ]] && found_comment=true
    ;;
  tf|hcl)
    result=$(printf '%s\n' "$check_content" | grep -E "$HASH_PAT|$SLASH_PAT" | grep -vE "$HASH_PRAGMA|$SLASH_PRAGMA" || true)
    [[ -n "$result" ]] && found_comment=true
    ;;
  java|js|ts|tsx|jsx|kts)
    result=$(printf '%s\n' "$check_content" | grep -E "$SLASH_PAT" | grep -vE "$SLASH_PRAGMA" || true)
    [[ -n "$result" ]] && found_comment=true
    ;;
esac

if [[ "$found_comment" != true ]]; then
  case "$ext" in
    py)
      result=$(printf '%s\n' "$check_content" | grep -E "^[[:space:]]*('''|\"\"\")" || true)
      [[ -n "$result" ]] && found_comment=true
      ;;
    java|js|ts|tsx|jsx|kts|tf|hcl)
      result=$(printf '%s\n' "$check_content" | grep -E '/\*' | grep -vE "$BLOCK_PRAGMA" || true)
      [[ -n "$result" ]] && found_comment=true
      ;;
  esac
fi

[[ "$found_comment" != true ]] && exit 0

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/reminder-messages.sh
source "${HOOKS_DIR}/lib/reminder-messages.sh"

jq -n --arg ctx "$(reminder_fossilized_comments)" '{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": $ctx
  }
}'
