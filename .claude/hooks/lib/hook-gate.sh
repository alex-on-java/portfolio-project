# shellcheck shell=bash
# hook-gate.sh — Sourceable session-aware deduplication library for hooks.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/hook-gate.sh"
#   hook_gate <hook_id> <session_id> <strategy> [args...]
#
# Strategies:
#   once          — show on first invocation per session, suppress all subsequent
#   every <N>     — show on 1st invocation, then every Nth invocation (0-indexed)
#   offset_every <offset> <N> — show when invocation count % N == offset (0-indexed)
#   burst_then_every <burst> <N> — show first <burst> invocations, then every Nth after that
#
# Returns:
#   0 = show (caller should emit output)
#   1 = suppress (caller should stay silent)
#
# State directory: ~/.cache/claude-hooks/gate/<hook_id>/
# Auto-cleanup: files with mtime > 24h are removed on each call.

# No set -e / set -o pipefail here — this is a sourceable library.
# The caller's shell options apply.

hook_gate() {
  local hook_id="${1:?hook_gate: hook_id required}"
  local session_id="${2:?hook_gate: session_id required}"
  local strategy="${3:?hook_gate: strategy required}"
  shift 3

  local state_dir="${HOME}/.cache/claude-hooks/gate/${hook_id}"
  local count_file="${state_dir}/${session_id}.count"

  # Ensure state directory exists
  mkdir -p "$state_dir"

  # Auto-cleanup: remove files older than 24 hours, suppress all errors
  find "$state_dir" -maxdepth 1 -type f -mmin +1440 -delete 2>/dev/null || true

  case "$strategy" in
    once)
      # If count file exists, this session already fired → suppress
      if [[ -f "$count_file" ]]; then
        return 1
      fi
      # First invocation: create the file and show
      echo 0 > "$count_file"
      return 0
      ;;

    every)
      local n="${1:?hook_gate: 'every' strategy requires N argument}"

      # Read current count (0 if file doesn't exist)
      local count=0
      if [[ -f "$count_file" ]]; then
        count=$(< "$count_file")
      fi

      # Determine whether to show
      local show=1  # default: suppress
      if (( count % n == 0 )); then
        show=0
      fi

      # Increment and write back (always, regardless of show/suppress)
      (( ++count ))
      echo "$count" > "$count_file"

      return "$show"
      ;;

    offset_every)
      local offset="${1:?hook_gate: 'offset_every' strategy requires offset argument}"
      local n="${2:?hook_gate: 'offset_every' strategy requires N argument}"

      local count=0
      if [[ -f "$count_file" ]]; then
        count=$(< "$count_file")
      fi

      local show=1  # default: suppress
      if (( count % n == offset )); then
        show=0
      fi

      (( ++count ))
      echo "$count" > "$count_file"

      return "$show"
      ;;

    burst_then_every)
      local burst="${1:?hook_gate: 'burst_then_every' strategy requires burst argument}"
      local n="${2:?hook_gate: 'burst_then_every' strategy requires N argument}"

      local count=0
      if [[ -f "$count_file" ]]; then
        count=$(< "$count_file")
      fi

      local show=1  # default: suppress
      if (( count < burst )); then
        show=0
      elif (( (count - burst) % n == n - 1 )); then
        show=0
      fi

      (( ++count ))
      echo "$count" > "$count_file"

      return "$show"
      ;;

    *)
      echo "hook_gate: unknown strategy '$strategy' — failing open (showing)" >&2
      return 0
      ;;
  esac
}
