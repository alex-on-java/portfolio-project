# shellcheck shell=bash
# hook-state.sh — Sourceable session-aware hook state library.
#
# Manages invocation counters and gating decisions for Claude Code hooks.
# Each hook registers with a unique hook_id; state persists per session.
#
# Usage:
#   source "$(dirname "${BASH_SOURCE[0]}")/../lib/hook-state.sh"
#   hook_gate <hook_id> <scope_key> <condition> [args...] [<condition> [args...]]...
#
# Conditions (all are AND-combined — all must pass for the gate to fire):
#   once                       — fire on first invocation per session only
#   every <N>                  — fire when invocation count % N == 0
#   burst_then_every <B> <N>   — fire first B invocations, then every Nth after that
#   cooldown <SECS>            — fire only if at least SECS seconds have passed since the last fire
#
# Returns:
#   0 = fire (all conditions passed); also sets HOOK_GATE_FIRES (0-indexed fire count)
#   1 = suppress (at least one condition failed)
#
# The invocation counter always advances on every call regardless of gate decision.
# HOOK_GATE_FIRES is only set when the gate fires — callers use it for message rotation.
#
# State directory: ~/.cache/claude-hooks/gate/<hook_id>/
# Auto-cleanup: files with mtime > 24h are removed on each call.

# No set -e / set -o pipefail here — this is a sourceable library.
# The caller's shell options apply.

hook_gate() {
  local hook_id="${1:?hook_gate: hook_id required}"
  local scope_key="${2:?hook_gate: scope_key required}"
  shift 2

  local state_dir="${HOME}/.cache/claude-hooks/gate/${hook_id}"
  local count_file="${state_dir}/${scope_key}.count"
  local fires_file="${state_dir}/${scope_key}.fires"
  local cooldown_file="${state_dir}/${scope_key}.last_fire"

  # Ensure state directory exists
  mkdir -p "$state_dir"

  # Auto-cleanup: remove files older than 24 hours, suppress all errors
  find "$state_dir" -maxdepth 1 -type f -mmin +1440 -delete 2>/dev/null || true

  # Read current invocation count (0-indexed: first call sees count=0)
  local count=0
  [[ -f "$count_file" ]] && count=$(< "$count_file")

  # Evaluate all conditions with AND logic.
  # Any failing condition sets pass=false; the rest are still evaluated
  # so that every condition's argument count is consumed correctly.
  local pass=true

  while (( $# > 0 )); do
    case "$1" in
      once)
        shift
        if (( count > 0 )); then pass=false; fi
        ;;

      every)
        shift
        local _n="${1:?hook_gate: 'every' requires N}"
        shift
        if (( count % _n != 0 )); then pass=false; fi
        ;;

      burst_then_every)
        shift
        local _burst="${1:?hook_gate: 'burst_then_every' requires burst count}"
        local _period="${2:?hook_gate: 'burst_then_every' requires period N}"
        shift 2
        # In burst phase: always passes. After burst: passes every _period-th step.
        if (( count >= _burst )) && (( (count - _burst) % _period != _period - 1 )); then
          pass=false
        fi
        ;;

      cooldown)
        shift
        local _secs="${1:?hook_gate: 'cooldown' requires SECS}"
        shift
        if [[ -f "$cooldown_file" ]]; then
          local _last _now
          _last=$(< "$cooldown_file")
          _now=$(date +%s)
          if (( _now - _last < _secs )); then pass=false; fi
        fi
        ;;

      *)
        echo "hook_gate: unknown condition '$1' — failing open (showing)" >&2
        shift
        ;;
    esac
  done

  # Counter always advances, regardless of gate decision
  (( ++count ))
  echo "$count" > "$count_file"

  if $pass; then
    # Track fire count for message rotation; expose 0-indexed value to caller
    local _fires=0
    [[ -f "$fires_file" ]] && _fires=$(< "$fires_file")
    export HOOK_GATE_FIRES=$_fires
    (( ++_fires ))
    echo "$_fires" > "$fires_file"
    # Update cooldown timestamp so subsequent calls respect the cooldown window
    date +%s > "$cooldown_file"
    return 0
  else
    return 1
  fi
}
