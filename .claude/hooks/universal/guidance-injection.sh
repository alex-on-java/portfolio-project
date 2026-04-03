#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# guidance-injection.sh — SessionStart hook.
# Injects guidance documents (working principles, project policies) as additional
# context at session boundaries so the agent internalizes them early.
#
# Designed for extensibility: to inject a new document, add it to GUIDANCE_FILES.

# Consume stdin (hook input) — currently unused but available for future
# differentiation between startup/clear/etc.
cat > /dev/null

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "${HOOKS_DIR}/../.." && pwd)"

# Guidance documents to inject, in order.
GUIDANCE_FILES=(
  "${PROJECT_ROOT}/docs/WORKING_PRINCIPLES.md"
  "${PROJECT_ROOT}/docs/PROJECT_POLICIES.md"
)

combined=""
for file in "${GUIDANCE_FILES[@]}"; do
  if [[ -f "$file" ]]; then
    content=$(<"$file")
    if [[ -n "$combined" ]]; then
      combined+=$'\n\n---\n\n'
    fi
    combined+="$content"
  else
    echo "guidance-injection: file not found, skipping: $file" >&2
  fi
done

# If no documents were found, exit silently — nothing to inject
[[ -n "$combined" ]] || exit 0

jq -n --arg ctx "$combined" \
  '{
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": $ctx
    }
  }'
