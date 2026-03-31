#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# PreToolUse hook: blocks `git commit` unless the Bash tool description
# contains the intentional-commits skill confirmation string.
#
# Input:  JSON on stdin (PreToolUse payload with tool_input.command and tool_input.description)
# Output: exit 0 = allow, exit 2 = block (stderr message fed back to agent)

readonly CONFIRMATION="I hereby confirm that I invoked skill intentional-commits"

input=$(cat)

command=$(echo "$input" | jq -r '.tool_input.command // ""')
description=$(echo "$input" | jq -r '.tool_input.description // ""')

# Check if the command involves a git commit.
# Simple heuristic: both "git" and "commit" appear in the command string.
# False positives (e.g., git commit-tree) are acceptable — the agent just
# gets asked to invoke the skill, which is harmless.
if echo "$command" | grep -qi 'git' && echo "$command" | grep -qi 'commit'; then
  if [[ "$description" != *"$CONFIRMATION"* ]]; then
    echo "You are about to commit, but seems like you forgot to invoke a mandatory skill" >&2
    echo "You **must** invoke the 'intentional-commits' skill before committing." >&2
    echo "If this blocker a false positive, invoke the skill nonetheless" >&2
    exit 2
  fi
fi

exit 0
