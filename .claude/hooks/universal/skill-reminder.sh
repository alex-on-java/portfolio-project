#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# skill-reminder.sh — UserPromptSubmit hook.
# Data-driven skill reminder: reads lib/skill-reminders.json,
# matches patterns against the user's prompt, and injects
# one-time-per-skill-per-session reminders for matched skills.

input=$(cat)

prompt=$(echo "$input" | jq -r '.prompt // empty')
[[ -z "$prompt" ]] && exit 0

session_id=$(echo "$input" | jq -r '.session_id // empty')
agent_id=$(echo "$input" | jq -r '.agent_id // empty')
scope_key="${session_id}:${agent_id}"

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

config_file="${HOOKS_DIR}/lib/skill-reminders.json"
[[ ! -f "$config_file" ]] && exit 0

# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

reminders=()

while IFS= read -r entry; do
  pattern=$(echo "$entry" | jq -r '.pattern // empty')
  trigger=$(echo "$entry" | jq -r '.trigger // empty')
  skill=$(echo "$entry" | jq -r '.skill // empty')

  [[ -z "$pattern" || -z "$trigger" || -z "$skill" ]] && continue

  if ! echo "$prompt" | grep -qiE -- "$pattern"; then
    continue
  fi

  if ! hook_gate "skill-reminder" "${scope_key}:${skill}" once; then
    continue
  fi

  reminders+=("User mentioned ${trigger}. Consider using the \`${skill}\` skill.")
done < <(jq -c '.[]' "$config_file")

[[ ${#reminders[@]} -eq 0 ]] && exit 0

context=$(IFS=$'\n'; printf '%s' "${reminders[*]}")

jq -n --arg ctx "$context" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "UserPromptSubmit",
      "additionalContext": $ctx
    }
  }'
