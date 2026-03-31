#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# hook-dispatcher.sh — Environment-aware hook router.
#
# Usage (in .claude/settings.json):
#   "$CLAUDE_PROJECT_DIR"/.claude/hooks/hook-dispatcher.sh <relative-path>
#
# Routing rules:
#   universal/*  → always execute
#   local/*      → execute only when CLAUDE_CODE_REMOTE is NOT set (local dev)
#   cloud/*      → execute only when CLAUDE_CODE_REMOTE IS set (Claude Code web)
#
# Passes stdin, stdout, stderr, and exit code through to the target script.

if [[ $# -lt 1 ]]; then
  echo "Usage: hook-dispatcher.sh <relative-hook-path>" >&2
  exit 1
fi

readonly HOOK_REL_PATH="$1"
shift

# Resolve absolute path to the target hook
HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TARGET="${HOOKS_DIR}/${HOOK_REL_PATH}"

if [[ ! -f "$TARGET" ]]; then
  echo "hook-dispatcher: target not found: $TARGET" >&2
  exit 1
fi

# Extract environment prefix (first path component)
readonly ENV_PREFIX="${HOOK_REL_PATH%%/*}"

# Determine if we're in cloud
is_cloud=false
if [[ -n "${CLAUDE_CODE_REMOTE+x}" ]]; then
  is_cloud=true
fi

# Routing decision
case "$ENV_PREFIX" in
  universal)
    # Always run
    ;;
  local)
    if [[ "$is_cloud" == "true" ]]; then
      exit 0  # Skip local hooks in cloud
    fi
    ;;
  cloud)
    if [[ "$is_cloud" == "false" ]]; then
      exit 0  # Skip cloud hooks locally
    fi
    ;;
  *)
    echo "hook-dispatcher: unknown environment prefix '$ENV_PREFIX' in '$HOOK_REL_PATH'" >&2
    echo "hook-dispatcher: expected one of: universal, local, cloud" >&2
    exit 1
    ;;
esac

# Execute the target hook, passing through stdin, all remaining args, and preserving exit code
exec "$TARGET" "$@"
