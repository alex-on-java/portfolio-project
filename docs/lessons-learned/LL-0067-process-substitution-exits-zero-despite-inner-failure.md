# LL-0067: Bash Process Substitution Swallows Inner Command Failure Under `set -Eeuo pipefail`

**Summary**: Process substitution (`< <(cmd)`) runs the inner command in a subshell whose exit code Bash discards. `pipefail`, `errexit`, and the `ERR` trap each operate on the outer command, so a failing network call inside process substitution produces an empty pipe and a zero outer exit. The outer script continues as if the command succeeded. Hoisting fallible commands out of process substitution into plain `$(...)` assignments restores the error-propagation guarantee that `set -Eeuo pipefail` is assumed to provide.

## What Happened

The `cleanup-image-artifacts` job in `.github/workflows/ci-pr.yml` deleted workflow-run artifacts via a `gh api` call inside process substitution:

```bash
while IFS= read -r name; do
  # delete each artifact
done < <(gh api "/repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/artifacts" --jq '.artifacts[].name')
```

Under `set -Eeuo pipefail`, a `gh api` failure (revoked token, API outage, permissions regression) caused the process substitution to produce an empty pipe. Zero iterations meant a zero exit from the `while` loop. The cleanup step reported success, no artifact was deleted, and no error appeared in the log.

## Root Cause

Process substitution runs the inner command in a subshell connected to the outer command via a file descriptor, not through a pipeline in the sense that `pipefail` monitors. Bash discards the subshell exit status before the outer command begins. `set -e` fires only on the outer command's exit status, which is the `while` loop's own exit (0 after zero iterations). The `ERR` trap and `pipefail` follow the same boundary: neither sees inside the subshell.

The combination `set -Eeuo pipefail` is widely treated as "strict mode." It closes several error-propagation gaps, but process substitution is a gap it does not close. A fallible command inside `< <(...)` is as invisible to the outer script as if error handling were absent entirely.

## Resolution

The fix hoisted the `gh api` call out of process substitution into a plain variable assignment:

```bash
artifacts=$(gh api "/repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/artifacts" --jq '.artifacts[].name')
while IFS= read -r name; do
  # delete each artifact
done <<< "$artifacts"
```

A non-zero exit from `gh api` now surfaces as a non-zero exit from the assignment statement, which `set -e` catches. The script aborts at that line, with the error visible in the log. Iteration structure stays the same: the `while` loop reads from a here-string (`<<<`) fed by the variable.

## How to Detect

Scan any bash script running under `set -e` or `set -Eeuo pipefail` for the pattern `< <(`. For each match, ask whether the inner command can fail (a network call, a file read, a subprocess that returns non-zero). If it can, the failure is silently swallowed. The symptom is a step that exits 0 and produces no output, where a successful inner command would have produced output. Absence of output without an error is the signal.

## Adoption Rule

Do not place fallible commands inside process substitution in scripts that rely on `set -e` for error propagation. Hoist the command into a `$(...)` assignment, where its exit code is visible to the shell's error machinery. Reserve process substitution for cases where the inner command's failure is genuinely ignorable, and document that intention with a comment. Process substitution belongs to a family of bash constructs that circumvent `set -e`: `$(...)` in certain positions, commands on the left side of `&&` or `||`, and commands inside `if` conditions. `set -Eeuo pipefail` leaves these gaps intact; each requires an explicit structural choice, not reliance on the mode flags.
