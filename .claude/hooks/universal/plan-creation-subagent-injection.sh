#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# plan-creation-subagent-injection.sh — PreToolUse hook for Skill.
# Injects the session sub-agent list as additional context when the
# plan-creation skill is loaded, since the agent doesn't know its own
# sub-agent transcript paths natively.

input=$(cat)

skill_name=$(echo "$input" | jq -r '.tool_input.skill // empty')

# Only fire for the plan-creation skill
[[ "$skill_name" == "plan-creation" ]] || exit 0

transcript_path=$(echo "$input" | jq -r '.transcript_path // empty')

# If transcript path is missing, nothing useful to inject
[[ -n "$transcript_path" ]] || exit 0

session_id=$(basename "$transcript_path" .jsonl)
subagents_dir="$(dirname "$transcript_path")/${session_id}/subagents"

# No sub-agents yet — silent no-op
[[ -d "$subagents_dir" ]] || exit 0

# Collect .meta.json files
mapfile -t meta_files < <(find "$subagents_dir" -maxdepth 1 -name '*.meta.json' | sort)

# No sub-agents — silent no-op
[[ ${#meta_files[@]} -gt 0 ]] || exit 0

# Build list entries
entries=()
for meta_file in "${meta_files[@]}"; do
    agent_type=$(jq -r '.agentType // "Unknown"' "$meta_file")
    description=$(jq -r '.description // ""' "$meta_file")
    filename=$(basename "${meta_file%.meta.json}.jsonl")
    entries+=("- [${agent_type}] ${description} — ${filename}")
done

list=$(printf '%s\n' "${entries[@]}")

ctx="Please include the text in a code fence below into the **Conducted Research and Experiments** section:
\`\`\`
Enclosing folder: ${subagents_dir}
${list}
\`\`\`
Feel free to add any additional context for clarity
"

jq -n --arg ctx "$ctx" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": $ctx
    }
  }'
