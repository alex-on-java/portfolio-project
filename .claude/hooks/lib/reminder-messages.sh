# shellcheck shell=bash
# reminder-messages.sh — Sourceable library of reminder texts for session hooks.
#
# Usage:
#   source "${HOOKS_DIR}/lib/reminder-messages.sh"
#   message=$(reminder_north_star_principles)

# No set -e / set -o pipefail here — this is a sourceable library.
# The caller's shell options apply.

reminder_north_star_principles() {
  cat <<'REMINDER'
Working Principles (docs/WORKING_PRINCIPLES.md) are the North Star for every decision in this project. In long sessions, context drifts and early guidance loses salience — re-read the principles before making implementation decisions to ensure alignment.
REMINDER
}
