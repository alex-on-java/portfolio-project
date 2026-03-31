#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# precommit-policy-reminder.sh — PreToolUse hook for Bash.
# Fires once per session when a Bash command invokes a linter directly,
# nudging the agent toward `prek` as the single entry point for static analysis.

input=$(cat)

command_str=$(echo "$input" | jq -r '.tool_input.command // empty')
session_id=$(echo "$input" | jq -r '.session_id // empty')

# Already using the right entry point — nothing to nudge about
if echo "$command_str" | grep -qi 'prek'; then
  exit 0
fi

# Only fire if the command mentions a known linter
if ! echo "$command_str" | grep -qiE '\b(shellcheck|actionlint|hadolint|yamllint|pylint|flake8|mypy|ruff|eslint|prettier|black|isort|markdownlint|tflint|checkov|pyflakes|autopep8|biome)\b'; then
  exit 0
fi

# Source the gate library
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/hook-state.sh
source "${HOOKS_DIR}/lib/hook-state.sh"

# Once per session
if ! hook_gate precommit-policy-reminder "$session_id" once; then
  exit 0
fi

jq -n --arg ctx 'Heads up: this project uses `prek` as the single entry point for static analysis (see docs/PROJECT_POLICIES.md).

Before running linters directly, check .pre-commit-config.yaml — if the check is already configured there, `prek run --all-files` covers it. If a useful check is missing from the config, consider proposing to add it rather than running it ad-hoc.

This is a nudge, not a hard block — direct invocation is fine when you have a good reason (e.g., targeted single-file check, exploring a new tool).' \
  '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "additionalContext": $ctx
    }
  }'
