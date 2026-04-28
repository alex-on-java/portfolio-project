# shellcheck shell=bash
# reminder-messages.sh — Sourceable library of reminder texts for session hooks.
#
# Usage:
#   source "${HOOKS_DIR}/lib/reminder-messages.sh"
#   message=$(reminder_north_star_principles)
#   message=$(reminder_verification_persistence "$HOOK_GATE_FIRES")

# No set -e / set -o pipefail here — this is a sourceable library.
# The caller's shell options apply.

reminder_fossilized_comments() {
  cat <<'REMINDER'
You're adding comments; do not forget about the working principle "Comments Fossilize Context"

Reconsider:
- "Why" explanations → commit message is the right place, tied to a changeset
- Restating what the code does → redundant
- Javadoc / docstrings → redundant

Fine to keep:
- Section dividers that group related code
- Version number for sha: digests

If the comments were already here — "Leave The Code Better Than You Found It" still applies.

If you are not sure whether this comment belongs, either drop it, or read docs/code-quality-policies/CQP-002-no-fossilized-comments.md.
REMINDER
}

reminder_linter_silencers() {
  cat <<'REMINDER'
You're adding a linter silencer (e.g. # noqa, # type: ignore, // eslint-disable, // @ts-ignore, @SuppressWarnings); do not forget about the code-quality policy "Linter silencers are a last resort".

A silencer is rarely the right move. Walk the decision framework first:
- Refactor: bundle, split, or delete the code the rule is objecting to
- Named symbol: replace the bare form with an explicit, structured one (e.g. except (Exception,) via a named ABSORBED_FAULTS tuple)
- Configured before inline: file-wide or rule-wide silencers belong in pyproject.toml / .eslintrc, not next to one occurrence
- Tool disagreement: align config across overlapping tools instead of pragma-ing the source
- Framework-aware escape hatch: many rules have purpose-built knobs (e.g. runtime-evaluated base classes) that exempt only the legitimate shape

If a silencer is genuinely the only honest answer, it requires explicit human authorization recorded in the commit message, plus a breadcrumb comment pointing to the rationale. Agents must not add silencers unilaterally.

If you are not sure whether this silencer belongs, either fix the code, or read docs/code-quality-policies/CQP-001-no-linter-silencers.md.
REMINDER
}

reminder_north_star_principles() {
  cat <<'REMINDER'
Working Principles (docs/WORKING_PRINCIPLES.md) are the North Star for every decision in this project. In long sessions, context drifts and early guidance loses salience — re-read the principles before making implementation decisions to ensure alignment.
REMINDER
}

# reminder_verification_persistence <fire_index>
# Returns one of 3 rotating reminders encouraging the agent not to give up
# when Bash commands fail during verification. fire_index is 0-indexed
# (use HOOK_GATE_FIRES from hook_gate).
reminder_verification_persistence() {
  local index=$(( ${1:-0} % 3 ))
  case "$index" in
    0) cat <<'REMINDER'
A Bash command failed — this is expected during iterative verification. Analyze the error output carefully, adjust your approach, and retry. Do not abandon the verification step or ask the user to check manually.
REMINDER
      ;;
    1) cat <<'REMINDER'
Verification failures are data points, not stop signs. Read the error carefully, form a hypothesis about the root cause, and try a different approach. You have not exhausted your options.
REMINDER
      ;;
    2) cat <<'REMINDER'
A tool failure during verification means dig deeper, not give up. Step back, re-examine your assumptions about what should be true, and attempt another path to confirm the result.
REMINDER
      ;;
  esac
}
