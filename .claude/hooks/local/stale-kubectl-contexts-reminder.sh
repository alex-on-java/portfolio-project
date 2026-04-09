#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# stale-kubectl-contexts-reminder.sh — PreToolUse hook for Bash.
# Fires once per session when `kubectl config get-contexts` is invoked,
# reminding the agent that local kubeconfig contexts may be stale
# and that `gcloud` is the authoritative way to access GKE clusters.

input=$(cat)

command_str=$(echo "$input" | jq -r '.tool_input.command // empty')
session_id=$(echo "$input" | jq -r '.session_id // empty')
agent_id=$(echo "$input" | jq -r '.agent_id // empty')
scope_key="${session_id}:${agent_id}"

if ! echo "$command_str" | grep -qiE 'kubectl\s.*config\s.*get-contexts'; then
  exit 0
fi

# Source the gate library
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

# Once per session
if ! hook_gate stale-kubectl-contexts-reminder "$scope_key" once; then
  exit 0
fi

jq -n --arg ctx 'Heads up: `kubectl config get-contexts` reads locally cached kubeconfig entries that may be stale (deleted clusters, expired credentials, leftover contexts from old projects). This output is not authoritative for GKE access.

If you need to reach a GKE cluster, use `gcloud container clusters get-credentials` to establish a fresh, valid context.' \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": $ctx
    }
  }'
