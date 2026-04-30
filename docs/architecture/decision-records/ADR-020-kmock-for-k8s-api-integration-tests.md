---
status: accepted
date: 2026-04-30
decision-makers: [alex-on-java]
---

# kmock for K8s API Integration Tests in convergence-checker

## Context and Problem Statement

The convergence-checker's evaluator classifies cluster state across ArgoCD `Application` and Kargo `Stage` resources. Misclassification has direct merge-gate consequences (see `ADR-019`), so the evaluator's interaction with the K8s API needs failure-mode coverage in tests — not only mocked unit tests at the function-call level.

That requirement landed on a tooling question: which fake or real K8s API surface drives the integration test? The candidates span four distinct mechanisms (in-process Python fake, Go-based fake apiserver, real apiserver + etcd, real apiserver + etcd with fake kubelets), each with different fidelity, runtime, and setup costs. The comparison was carried out as four parallel proof-of-concepts in dedicated worktrees; this ADR records the decision the comparison produced.

## Decision Drivers

- **Sub-second test runtime** for CI feedback. The test runs on every push; a 5-second test is tolerable, a 30-second test is not.
- **CRD support** for `argoproj.io` and `kargo.akuity.io` types. Without CRD list endpoints, the evaluator's discovery code path is untestable.
- **Self-containment** — no kubeconfig, no fixed-port containers, no FS state. Parallel `pytest` workers must not collide.
- **Stateful K8s modeling** — `PATCH` must be visible to the next `GET`; `LIST` must return seeded items.
- **Faithfulness within the tested scope** — false negatives (test passes, prod fails) are the catastrophic class for an evaluator.
- **Maintenance budget** — workarounds and version pins live in `tests/` forever; the framework must not require disproportionate scaffolding.

## Considered Options

1. **`pachyderm/fakeapiserver`** — a Go-based in-process kube-apiserver mock.
2. **`kwok` (Kubernetes WithOut Kubelet)** — real `kube-apiserver` + `etcd`, fake nodes/kubelets.
3. **`envtest` (controller-runtime)** — real `kube-apiserver` + `etcd` with TLS scaffolding.
4. **`kmock` (by `nolar`, the Kopf maintainer)** — Python-native in-process fake with stateful K8s modeling.

## Decision Outcome

**Option 4 — `kmock`**, pinned to an exact version (`kmock==0.7.0`).

The rationale is the conjunction of the drivers: kmock is the only candidate that hits sub-second runtime, runs entirely in-process (no Docker, no kubeconfig, no fixed port), models stateful K8s for `PATCH`/`GET` semantics, and supports CRD list endpoints once `kmock.resources` is populated with `kind` + `namespaced`. Faithfulness within the convergence-checker's scope (CRD reads, `ConfigMap` PATCH on flat `.data`) was verified empirically; out-of-scope quirks are documented in `LL-0034`.

The framework was selected for one initial integration test (the failure-mode PoC slot from the charter). Adoption rules and known workarounds for scaling beyond one test live in `LL-0034`.

### Consequences

- **Good**: integration test runs in <1 second; CI feedback loop unaffected by the new test.
- **Good**: in-process, in-memory state — no Docker, no kubeconfig, no port collisions, parallel `pytest` workers safe.
- **Good**: failure-mode coverage closes the highest-risk class for the evaluator (cluster reports broken state, evaluator must classify).
- **Bad**: HTTPS unsupported; tests use `http://` and `verify_ssl=False`. Acceptable in-test, but production code that branches on `cfg.host.startswith("https://")` would invalidate the framework choice.
- **Bad**: kmock's fixture is async; the kubernetes Python SDK is sync. Tests cross the boundary via AnyIO's `start_blocking_portal` — a `BlockingPortal` enters kmock's async context managers from a synchronous fixture and yields a sync handle the test body uses (`tests/integration/test_kmock_failure.py`). The bridge is captured once in the fixture; the test itself stays synchronous (see `LL-0034`).
- **Bad**: kmock 0.7 (Jan 2026) is early-stage; `kmock==0.7.0` (3-segment) is required because the project's pinning policy regex demands `X.Y.Z` (PEP 440 normalizes both).

## Pros and Cons of the Options

### `pachyderm/fakeapiserver`

- **Good**: in-process Go fake; would have been performant.
- **Bad**: no API extension server. All three CRD lists (`argoproj.io`, `kargo.akuity.io`) would 404 — fatal for the evaluator's discovery path. Verified from `main.go` without building (the source confirmed the limitation directly).
- **Bad**: pinned to Kubernetes 1.23.1; 5–40 min compile from source on the first run; hardcoded `/tmp/kubeconfig` symlink; TLS CA marked `// TODO: make this work ;)`; last commit Jan 2022.

### `kwok`

- **Good**: real `kube-apiserver` semantics; faithful by construction.
- **Bad**: kwok's distinguishing value is fake-node/fake-kubelet simulation. The convergence-checker reads CRD `.status` only, never schedules pods — the value proposition is unused.
- **Bad**: same boot cost as `envtest` (real `kube-apiserver` + `etcd`); the dimension that distinguishes kwok from envtest is not exercised here. PoC stalled before delivery.

### `envtest` (controller-runtime)

- **Good**: real-apiserver fidelity; caught a real bug during the PoC (RFC 1123 namespace name validation rejected `app-A`, surfacing a coupling that fakes would have hidden).
- **Good**: test passed end-to-end in ~5 seconds; coverage delta 65% → 74%.
- **Bad**: ~80 LoC of cert-builder code required (macOS Python's OpenSSL demands `SubjectKeyIdentifier`/`AuthorityKeyIdentifier` extensions where Go's TLS is lenient). The setup tax is paid once but lives in `tests/` forever.
- **Bad**: namespace deletion hangs without explicit fixture-scoped cleanup; recommended pattern is fresh names per test plus session-scoped fixtures.
- **Bad**: ~5s per test run vs kmock's sub-second; a few seconds in absolute terms but compounds across many integration tests and parallel CI workers.

### `kmock`

See **Decision Outcome** above.

## More Information

- `ADR-019` — the gate's overall design that creates the requirement for evaluator integration tests.
- `LL-0034` — kmock platform quirks and adoption rules for scaling beyond the first integration test.
- The PoC sources lived in dedicated worktrees and are referenced only via prior session transcripts; the comparative reasoning was not preserved in any single commit message.
