#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# intermediate-commits-transcript-injection.sh — PreToolUse hook for Skill.
# Injects the session transcript path as additional context when the
# intermediate-commits skill is loaded, since skills don't receive it natively.

input=$(cat)

skill_name=$(echo "$input" | jq -r '.tool_input.skill // empty')

# Only fire for the intermediate-commits skill
[[ "$skill_name" == "intermediate-commits" ]] || exit 0

transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

# If transcript path is missing, nothing useful to inject
[[ -n "$transcript_path" ]] || exit 0

jq -n --arg ctx "Session transcript path: ${transcript_path}" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": $ctx
    }
  }'
