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
  "${PROJECT_ROOT}/docs/AGENT_OPERATING_POLICIES.md"
  "${PROJECT_ROOT}/docs/code-quality-policies/README.md|## Entries"
  "${PROJECT_ROOT}/docs/architecture/decision-records/README.md|## Decision Records"
)

slice_file() {
  local file="$1" anchor="$2" title rest
  title=$(head -n 1 "$file")
  rest=$(awk -v a="$anchor" 'found { print; next } $0 == a { found = 1 }' "$file")
  if [[ -z "$rest" ]]; then
    echo "guidance-injection: anchor not found in $file: $anchor" >&2
    return 1
  fi
  printf '%s\n\n%s' "$title" "$rest"
}

combined=""
for entry in "${GUIDANCE_FILES[@]}"; do
  file="${entry%%|*}"
  anchor=""
  [[ "$entry" == *"|"* ]] && anchor="${entry#*|}"

  if [[ ! -f "$file" ]]; then
    echo "guidance-injection: file not found, skipping: $file" >&2
    continue
  fi

  if [[ -n "$anchor" ]]; then
    content=$(slice_file "$file" "$anchor") || continue
  else
    content=$(<"$file")
  fi

  if [[ -n "$combined" ]]; then
    combined+=$'\n\n---\n\n'
  fi
  combined+="$content"
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
