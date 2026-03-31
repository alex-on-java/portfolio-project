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
CLAUDE.md contains holistic principles that should be treated as a North Star across the whole session. Before making implementation decisions, revisit these principles to ensure alignment.
REMINDER
}
