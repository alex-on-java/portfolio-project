---
status: accepted
date: 2026-07-01
decision-makers: [alex-on-java]
---

# Rendered Conftest Validation by Input Shape

## Context and Problem

The validation pipeline checks two different artifact shapes. Pre-commit hooks run Conftest against raw source files such as YAML, TOML, Dockerfiles, and JSON. The Kubernetes validation suite renders Helm and Kustomize output first, then validates the combined rendered manifests.

Those shapes need different policy entrypoints. Raw source policies can inspect source-only fields such as Kustomize `images[].newTag`. Rendered policies see final Kubernetes resources, file names emitted by the renderer, and neutral data prepared by the Python validation layer. Running rules for the wrong shape either produces false results or forces every policy to carry defensive noise.

The project also had a bespoke rendered secrets validator in Python. It parsed rendered YAML, carried workload Secret Manager constants, and emitted custom assertions. That shape made Python both the adapter and the policy engine. This decision replaces that path with one generic rendered Conftest bridge and puts project-specific rendered contracts in Rego.

## Decision Drivers

- The package name must identify the input shape, not collide with repository lifecycle vocabulary.
- Raw source validation remains useful and must stay separate from rendered manifest validation.
- The Python validation layer should prepare inputs and invoke tools; it should not become the home for project-specific Kubernetes contracts.
- One rendered Conftest bridge should support many rendered policies without adding a new Python validator for each contract.
- Policy-only edits must affect the GitOps lint and CI targets that read those policies at runtime.

## Decision

Conftest policies are split by input shape. Raw source policies use `package raw_sources`. The pre-commit hooks invoke Conftest with `--namespace raw_sources`, so the source-level checks do not depend on the default `main` namespace in Conftest. Rendered manifest policies use `package rendered_sources`. The Kubernetes validator invokes Conftest with `--combine --namespace rendered_sources` over the rendered output directory. It also passes neutral render-contract data with `--data`, currently the discovered overlay paths needed by rendered policies.

Python validation owns discovery, rendering, schema preparation, data preparation, and tool invocation. Project-specific correctness rules live in policy files and policy tests. The rendered secrets contract therefore moved from a Python validator into Rego. Shared policy logic lives in neutral helper packages when both source and rendered entrypoints need it. Container image parsing now lives under `policy.container_images`, with thin `raw_sources` and `rendered_sources` adapters for their respective input shapes.

The GitOps lint and CI targets include Conftest policies in their affected inputs. A change to policy code or policy tests now marks those targets affected.

## Options Considered

1. Keep the previous package names and rely on Conftest defaults.
   That left two problems in place. The raw source package name `main` overlapped with the repository main lifecycle segment, and the rendered package name did not say that it expected rendered manifests. The old names also hid a Conftest behavior that matters here: result rules are selected by namespace. A `deny` rule in one package does not run just because another package is present in the policy directory.

2. Keep domain-specific Python validators for rendered contracts.
   This would preserve the wrong extension point. A Python file that discovers rendered files, parses YAML, carries project constants, checks semantic rules, and formats failures is a private validation engine. It forces the author of each future contract to decide whether the next rule belongs in Python, Rego, shell, or another place. The review rule behind rejecting that pattern is to prefer policy engines over bespoke validators for committed correctness rules.

3. Add a separate Python bridge per rendered policy.
   This would avoid some duplicated parsing inside each validator, but it would still make the Python layer policy-aware. Each bridge would know too much about one domain and would need its own tests, fixtures, and failure reporting.

4. Split Conftest packages by input shape and use one rendered bridge.
   With the chosen split, the adapter stays generic. The Python bridge prepares rendered manifests plus neutral data, then Conftest evaluates the selected Rego package. Each policy can grow in the tool-native surface while sharing one invocation contract.

## Consequences

### Good

- Raw and rendered policies have names that tell reviewers which input shape they expect.
- Explicit source-level hooks prevent the default namespace in Conftest from silently changing which rules run.
- Rendered contracts now share one bridge. Future rendered policies can add Rego and tests instead of adding another project-specific Python validator.
- Shared image-reference parsing is tested once and reused by both adapters. The rendered adapter validates image values that only appear after Helm or Kustomize rendering.
- Policy-only edits participate in affected-target routing for GitOps lint and CI.

### Neutral

- Rego files in the same package share one package namespace. Tests need policy-specific, production-distinct fixtures and assertions so one policy does not accidentally prove the behavior of another policy.
- This decision keeps rendered image validation generic. Operator-specific image fields are outside its scope because no branch-1 rendered consumer uses them.

## Postponed Effort

Later branches can add domain-specific rendered contracts. Those consumers should use the same `rendered_sources` bridge instead of changing the architecture accepted here.

## Related Records

- [LL-0045](../../lessons-learned/LL-0045-conftest-verify-crashes-with-object-get-type-error.md)
