# LL-0041: Pinning `jdx/mise-action` to a SHA Does Not Pin the Installed mise Binary

## Summary

Pinning `jdx/mise-action` to a commit SHA satisfies CQP-003 and silences zizmor, but the action still installs whatever mise version is current at run time. A SHA pin locks the wrapper; the `version:` input locks the tool the wrapper installs. Without the second pin, two CI runs minutes apart can install different mise binaries from an identical workflow file.

## What Happened

`.github/actions/setup-nx/action.yml` referenced `jdx/mise-action@1648a7812b9aeae629881980618f079932869151 # v4.0.1` with no `version:` input. The SHA pin was clean: zizmor passed, the CQP-003 "GitHub Actions are SHA-pinned" check was satisfied, and the file looked fully locked down. Meanwhile, the mise version installed by the action drifted with whatever resolution logic ran at the time, while the local toolchain ran a fixed `2026.4.20`. CI and local diverged with no diff to attribute the divergence to.

## Root Cause

`jdx/mise-action` is an installer-shaped action: the job is to fetch and install a separate binary, not to do work itself. Such actions expose two pin surfaces. One is the action reference (the `uses:` line), pinned by SHA. The other is the version of the tool the action installs, pinned by an action input; for `jdx/mise-action`, that input is `version:`.

CQP-003 and zizmor both inspect the `uses:` reference shape. Neither inspects what the action installs at run time, because no static signal in the workflow file says that the action does any installation at all. An action-only pin therefore looks complete by every static check and is still floating along the second axis. This is the transitively-pinned illusion: pinning the wrapper hides the moving part inside it.

## Resolution

Set the `version:` input on `jdx/mise-action` explicitly, alongside the SHA pin:

```yaml
- name: Install mise toolchain
  uses: jdx/mise-action@1648a7812b9aeae629881980618f079932869151 # v4.0.1
  with:
    version: 2026.4.20
```

Both pins are now load-bearing. Bumping mise is a conscious edit to the `version:` input, reviewable as a diff. The SHA pin and the version pin upgrade independently and intentionally.

## Generalization

The same dual-surface trap appears in every installer-shaped action. Audit the workflow for actions that install a separate tool, and pin both surfaces:

- `jdx/mise-action`: pin `version:` to a mise release.
- `asdf-vm/actions/install`: pin `asdf_branch:` and rely on a committed `.tool-versions` for the installed tools.
- `actions/setup-node`, `actions/setup-go`, `actions/setup-python`, and siblings: pin `node-version:` / `go-version:` / `python-version:` to an exact version, not a major or a `lts/*` alias. A `.nvmrc` or `.tool-versions` file is acceptable when it is itself pinned exactly and committed.
- `docker/setup-buildx-action`, `docker/setup-qemu-action`: pin the `version:` of the buildx or QEMU release, not just the action SHA.
- Any third-party "install tool X" action: assume it has an installer surface until proven otherwise.

## Adoption Rule

For any installer-shaped action, the tool-version input is as load-bearing as the SHA itself. CQP-003 compliance for such actions requires both pins, not one. When reviewing a workflow change, the question is not "is the `uses:` line SHA-pinned" but "is every version axis the action introduces pinned to an exact value".

## How to Detect

Signs that the pin surface of an action is incomplete:

- Two CI runs of the same workflow file produce different installed-tool versions, observable in setup-step logs.
- The documentation for the action describes a `version:` (or equivalent) input and the workflow does not set it.
- A local toolchain version (mise, asdf, `.nvmrc`) and the CI-installed version drift over time without any workflow diff.

When adding or reviewing a `uses:` line, read the `inputs:` block of the action. If any input controls the version of an installed tool, set it explicitly.
