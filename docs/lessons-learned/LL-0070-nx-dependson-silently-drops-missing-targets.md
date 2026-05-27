# LL-0070: Nx `dependsOn` silently drops references to missing targets

**Summary**: Nx resolves `dependsOn` entries against a project's declared targets at execution time. When a referenced target does not exist on the project, Nx drops the entry with no warning, no error, and no non-zero exit. The resolved dependency graph omits the missing target. `nx show project --json` still reports the full `dependsOn` array, making the gap invisible to configuration inspection alone. A safety gate that depends on this behavior is vacuous for any project that lacks the referenced target.

## What Happened

During CI gating work on branch `nx-redesign-paving-the-road`, the team extended each image-producing project's `publish-image` target to depend on lint and test:

```json
"publish-image": {
  "dependsOn": ["build-image", "lint", "test"]
}
```

The intent was to block image publish when the same project's lint or test failed. `convergence-checker`, which declares `lint`, `test`, and `build-image` targets, saw the gate work as expected. `web-app`, which declares only `build-image`, produced a different result. `nx show project web-app --json` reported `dependsOn: ["build-image", "lint", "test"]` in the configuration. At execution time, Nx silently ignored the missing targets. Running `nx run web-app:publish-image` proceeded as if `dependsOn` were `["build-image"]` alone. The gate was vacuous for `web-app`.

## Root Cause

Nx resolves `dependsOn` entries against the project's declared targets at execution time and silently drops any entry whose target the project does not declare. It produces no warning, no error, and no non-zero exit. The resolved dependency graph simply omits the missing entries.

`nx show project --json` reports the configured `dependsOn` array including the missing targets, which makes the gap invisible to inspection of the configuration alone. The configuration appears correct; the dependency graph is not.

This failure mode belongs to the same silent-acceptance class as LL-0042. In that case, `nx show projects --withTarget` accepted an unrecognized filter flag and emitted the full project list as if the filter were satisfied. Both cases share the same root behavior: Nx accepts a reference to something that does not exist, proceeds without it, and reports success.

## Resolution

The team abandoned per-project Nx-level gating. Commit `2da7ab3` on `nx-and-ci-redesign` moved cross-project safety to a workflow-level `pre-publish-gate` aggregator with no dependency on per-project target declarations. Each project's `ci` target declares `dependsOn` listing only targets the project actually owns (ADR-028).

## How to Detect

Run `nx run <project>:<target>` on a project where `dependsOn` references targets the project does not declare. When the target runs successfully without executing the referenced dependencies, Nx dropped them silently.

Comparing `nx show project <name> --json` output against `nx graph --targets` output for the same project reveals the gap: the configuration lists the dependency, but the resolved graph does not. The discrepancy is the signal.

## Adoption Rule

Declare only targets the project actually owns in `dependsOn`. Do not rely on `dependsOn` to enforce invariants across projects with different target sets. Verify the effective dependency graph with `nx graph` or by running the target and observing which dependencies execute. Inspecting `nx show project --json` alone is insufficient: it reflects configured intent, not executed behavior.

Safety invariants that must hold across projects with heterogeneous target sets belong at the CI workflow layer. At that layer, the invariant holds regardless of which targets each project owns.

## Relationship to LL-0042 and LL-0069

LL-0042 documents that `nx show projects --withTarget` silently drops unrecognized flags. The `targetDefaults` override behavior, where project-level `dependsOn` replaces rather than merges the workspace default, is documented in [LL-0069](LL-0069-nx-project-dependson-overrides-targetdefaults-not-merges.md). This entry adds a third silent-failure mode in the same tool: Nx drops missing targets in `dependsOn` at execution time without any signal. All three share the pattern of Nx accepting invalid or incomplete input and proceeding as if the input were correct.
