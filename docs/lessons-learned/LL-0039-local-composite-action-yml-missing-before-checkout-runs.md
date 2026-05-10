# LL-0039: A Local Composite GitHub Action Cannot Bootstrap Itself

## Summary

A local composite action at `./.github/actions/<name>` is loaded from the working tree at the moment the runner processes the `uses:` line. Before `actions/checkout` runs, that path does not exist on disk. Placing `actions/checkout` as the first step inside the composite is unreachable: the runner fails reading `action.yml` before any step inside the composite runs. Every caller job must run `actions/checkout` *before* the `uses: ./.github/actions/<name>` line.

## What Happened

The `setup-nx` composite was authored with `actions/checkout` as its first step. Wrapping all toolchain bootstrap (checkout, mise, pnpm install, nx affected base/head) in one composite was meant to keep callers DRY. Every caller job (`changes`, `lint`, `test`, `build`) failed at the "Set up nx" step with:

```
##[error]Can't find 'action.yml' under '.github/actions/setup-nx'.
Did you forget to run actions/checkout before running your local action?
```

The error wording sounds procedural, as if the *caller* forgot a step. In fact the problem is structural: no authoring of the composite can fix it, because the composite itself is the unreachable file.

## Root Cause

GitHub Actions resolves `uses: ./<path>` against the working tree of the runner at the moment the step is processed. Before `actions/checkout` runs, the working tree contains only runner scaffolding; `.github/actions/setup-nx/action.yml` is not present. The runner therefore cannot read the composite definition, cannot enumerate its steps, and cannot reach the `actions/checkout` step the composite would have run first. A composite that intends to bootstrap the workspace cannot bootstrap *itself*.

The error message is misleading by accident, not by design. Its phrasing ("Did you forget to run actions/checkout…") frames the problem as a missing caller-side step, which is the correct fix. It omits the structural reason: no in-composite ordering would have worked.

## Resolution

Lift `actions/checkout` out of the composite into every caller job. The composite handles only the steps that legitimately follow checkout (toolchain install, dependency install, nx affected base/head); the caller owns the precondition.

```yaml
# Caller (every job that uses the composite)
steps:
  - name: Checkout
    uses: actions/checkout@<pinned>
    with:
      fetch-depth: 0
      persist-credentials: false

  - name: Set up nx
    uses: ./.github/actions/setup-nx
```

```yaml
# .github/actions/setup-nx/action.yml
name: Set up nx workspace
description: Install mise toolchain, install node_modules, set nx affected base/head. Caller must run actions/checkout (fetch-depth 0) first.
runs:
  using: composite
  steps:
    - uses: jdx/mise-action@<pinned>
    - run: pnpm install --frozen-lockfile
      shell: bash
    - uses: nrwl/nx-set-shas@<pinned>
```

The `description:` field on the composite is the right place to record the precondition. It appears in the action metadata, sits next to the steps that depend on it, and is the first thing a future caller reads when they open `action.yml`.

## How to Detect

Any local composite that references the working tree (reads files, runs project scripts, depends on `node_modules`, derives git SHAs) has this constraint. The rule across the repository:

- Any local composite that touches the working tree requires the caller to run `actions/checkout` first.
- Record the precondition in the `description:` field of the composite, with the required `fetch-depth` and any other checkout options the downstream steps assume.
- When triaging the runner error `Can't find 'action.yml'… Did you forget to run actions/checkout`, read it as "caller-side checkout is missing," never as "the composite is broken internally."

A composite that needs no working-tree access (e.g., one that only calls third-party actions with literal inputs) is exempt, but such composites are rare. Treating the precondition as universal is cheaper than auditing each composite for working-tree dependencies.
