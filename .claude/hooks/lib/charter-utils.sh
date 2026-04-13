# shellcheck shell=bash
# charter-utils.sh — Sourceable library for Feature Charter resolution.
#
# Usage:
#   source "${HOOKS_DIR}/lib/charter-utils.sh"
#   charter_file=$(resolve_charter_path "$project_root")

resolve_charter_path() {
  local project_root="$1"
  local charters_dir="${project_root}/.claude/charters"

  local branch
  branch=$(git -C "$project_root" branch --show-current 2>/dev/null) || return 0
  [[ -n "$branch" ]] || return 0

  local sanitized="${branch//\//--}"
  local charter_file="${charters_dir}/${sanitized}.md"

  if [[ -f "$charter_file" ]]; then
    printf '%s' "$charter_file"
  fi
}
