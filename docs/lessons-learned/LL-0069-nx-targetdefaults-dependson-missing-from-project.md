# LL-0069: Nx Project-Level `dependsOn` Overrides `targetDefaults`, Does Not Merge

**Summary**: In Nx 22.7.1, when a project declares its own `dependsOn` for a target, that array completely replaces any `dependsOn` declared for the same target in `targetDefaults`. The two arrays do not merge. Other keys in the same `targetDefaults` block, such as `cache`, merge normally. The override behavior is specific to `dependsOn` and the documentation does not mark it as an intentional design choice. A workspace-level gate intended to guard every project's `publish-image` target was silently inert for every project that declared its own `dependsOn`.

## What Happened

During the CI redesign on branch `nx-redesign-paving-the-road`, the team added a workspace-level gate to `nx.json`:

```json
"targetDefaults": {
  "publish-image": {
    "cache": false,
    "dependsOn": ["lint", "test"]
  }
}
```

The intent was to make every project's `publish-image` target depend on `lint` and `test` in addition to whatever each project declared locally. Both `convergence-checker` and `web-app` already declared their own `publish-image` target with `dependsOn: ["build-image"]`.

Running `nx show project convergence-checker --json` and `nx show project web-app --json` showed that both projects reported `dependsOn: ["build-image"]` only. Both commands returned no `lint` or `test` entries from `targetDefaults`. Yet `cache: false` from the same `targetDefaults` block did appear in the effective configuration.

The workspace-level gate was silently inert for every project that declared its own `dependsOn`.

## Root Cause

In Nx 22.7.1, the effective configuration for a target merges `targetDefaults` and the project-level declaration key by key. For scalar keys, the project-level value overrides the default. The `dependsOn` key is different: a project-level `dependsOn` array discards the `targetDefaults` array entirely rather than appending to it.

Treating `targetDefaults` as defaults that projects extend is correct for scalar keys but wrong for `dependsOn`. The documentation omits any label for this as an intentional design choice. An engineer who reads `targetDefaults` as "baseline that projects augment" will write a workspace-level gate, observe that `cache` propagates correctly, and conclude the full block took effect.

The `nx show project` command exposes the resolved effective configuration, not the raw source. Inspecting it after any `targetDefaults` change is the only way to confirm what the executor will actually see.

## Resolution

The workspace-level `dependsOn` was removed from `targetDefaults`. Each project's `publish-image.dependsOn` was extended at the project level to include `lint` and `test` alongside `build-image`. Only projects that declare the named targets received the extended dependency, which avoided spurious failures on projects where `lint` or `test` did not exist.

In the final redesign (commit `2da7ab3` on `nx-and-ci-redesign`), the per-project Nx-level gate was replaced entirely by a workflow-level `pre-publish-gate` aggregator job. The project-level gate could not express cross-project safety (see ADR-028), and the `dependsOn` override behavior was one of several factors that drove the decision away from Nx-level gating.

## How to Detect

Run `nx show project <name> --json` and inspect the effective `dependsOn` for the target in question. Compare it against the `targetDefaults` declaration for the same target. When the project declares its own `dependsOn`, the `targetDefaults` entry is absent from the effective configuration.

The confirming check is:

```bash
nx show project <name> --json | jq '.targets["publish-image"].dependsOn'
```

A result that excludes entries declared in `targetDefaults` confirms the override is active. Running this check against every affected project after any change to `targetDefaults` or project-level `dependsOn` is the only reliable way to verify the effective graph.

## Adoption Rule

Do not rely on `targetDefaults.dependsOn` to inject universal dependencies across projects that declare their own `dependsOn` for the same target. After any change to `targetDefaults` or project-level `dependsOn`, verify the effective configuration with `nx show project <name> --json` for each affected project before treating the change as complete. For cross-project safety invariants that must hold regardless of individual project declarations, enforce them at the CI workflow layer rather than inside Nx dependency chains.
