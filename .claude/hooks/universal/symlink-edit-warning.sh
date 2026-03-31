#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# PostToolUse hook for Edit/Write: warns when the edited file is a symlink.
#
# Input:  JSON on stdin (PostToolUse payload with tool_input.file_path)
# Output: exit 0 always (non-blocking). If symlink detected, outputs JSON with
#         additionalContext so the agent sees the warning.

input=$(cat)

file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')
[[ -z "$file_path" ]] && exit 0

if [[ -L "$file_path" ]]; then
  # readlink (no flags) = immediate symlink target (relative, human-readable)
  # readlink -f = fully resolved absolute path (for git add command)
  link_target=$(readlink "$file_path")
  resolved=$(readlink -f "$file_path")

  jq -n --arg symlink "$file_path" --arg link "$link_target" --arg resolved "$resolved" '{
    "hookSpecificOutput": {
      "hookEventName": "PostToolUse",
      "additionalContext": ("SYMLINK DETECTED: `" + $symlink + "` is a symlink to `" + $link + "`. The real file on disk is `" + $resolved + "`. When staging for git, run `git add " + $resolved + "` (the target), not the symlink path.")
    }
  }'
fi

exit 0
