# LL-0034: kmock 0.7 platform quirks — adoption rules for in-process K8s API integration testing

## Summary

`kmock` (by `nolar`, the Kopf maintainer) is the recommended in-process K8s API fake for Python integration tests in this project (see `ADR-020` for the comparative decision). The tool's strengths — sub-second runtime, in-memory state, no Docker — come with known quirks that turn into hidden cost as test count grows. This LL documents what the first integration test surfaced, so the second test does not rediscover them.

## Quirks and how to handle them

### HTTPS is unsupported

kmock serves over plain HTTP. Tests configure the kubernetes client with `host="http://..."` and `verify_ssl=False`. **Adoption rule:** if production code branches on `cfg.host.startswith("https://")` (e.g., to gate certificate validation), kmock cannot exercise that branch — choose `envtest` for tests that must cross the TLS boundary.

### Async fixture only — kubernetes SDK is sync

kmock's lifecycle is async (the emulator and HTTP server are async context managers); the kubernetes Python SDK is sync. The clean bridge is AnyIO's `start_blocking_portal`: a `BlockingPortal` runs an asyncio event loop on a worker thread and exposes a synchronous handle. The fixture enters kmock's async context managers via `portal.wrap_async_context_manager(...)`, then yields a plain (sync) emulator handle to the test. The test body itself stays a regular `def test_...` — no `async`, no `asyncio.to_thread` per call site, no hand-rolled thread+loop bridge.

**Adoption rule:** use `start_blocking_portal(backend="asyncio")` inside an `ExitStack`-based fixture (the shape in `tests/integration/test_kmock_failure.py` is the reference). Avoid hand-rolled thread/loop bridges or per-call `asyncio.to_thread` wrappers — the BlockingPortal is the off-the-shelf primitive for this exact case (sync test driving an async-only library), and reaching for anything else multiplies the impedance into every call site.

### Version pinning regex demands 3-segment versions

kmock publishes `0.7` (PEP 440 normalizes to `0.7.0`), but the project's pinning policy regex (CQP-003) demands `X.Y.Z`. **Adoption rule:** pin as `kmock==0.7.0`, not `kmock==0.7`. The constraint is the project's, not kmock's; pre-1.0 libraries that publish 2-segment versions need this dance.

### ConfigMap PATCH content-type ambivalence

The kubernetes SDK uses `application/strategic-merge-patch+json` by default. kmock parses incoming PATCH bodies as JSON merge-patch internally. For a `ConfigMap` with a flat `.data` map, both interpretations produce identical results. For resources with list-of-dicts in `.spec` (e.g., `Pod.spec.containers[]`, `Deployment.spec.template.spec.containers[]`), the two patch types diverge — strategic-merge by name, JSON merge by replacement. **Adoption rule:** convergence-checker exercises only flat-map PATCH, so this divergence does not bite. A future test on Pod/Deployment specs needs to verify that kmock's PATCH semantics match real K8s for the specific list-of-dicts shape, or use `application/merge-patch+json` explicitly.

### Pre-create resources before PATCH

kmock returns 404 for PATCH-of-missing — faithful to real K8s. **Adoption rule:** seed every resource the test PATCHes during fixture setup. The convergence-checker's integration test pre-creates the heartbeat `ConfigMap` and `cluster-identity` `ConfigMap` in fixtures before any test code runs.

### CRD list endpoints require explicit registration

For CRD list endpoints (`argoproj.io/v1alpha1/applications`, `kargo.akuity.io/v1alpha1/stages`) to respond, `kmock.resources` must be populated with `kind` and `namespaced` for each CRD. **Adoption rule:** centralize CRD registration in a session-scoped fixture; the registration is identical across every test that reads the same CRD types.

### PyJWT signing requires a real RSA key

The convergence-checker generates GitHub App installation tokens via `jwt.encode(..., algorithm="RS256")`, which requires a private RSA key — even when GitHub itself is stubbed via `responses`. The first iteration generated a fresh key per test (~2s/test of CPU). **Adoption rule:** generate the key once in a session-scoped fixture. See `d02a569` for the `TokenProvider` Protocol seam that lets tests stub the token entirely instead of signing — the cleaner path when the test does not exercise the JWT signing pipeline.

### Ephemeral-port allocation is automatic

kmock allocates a fresh port per fixture instance. Parallel `pytest` workers do not collide. No `@pytest.mark.serial` or port-mutex needed.

### Strict admission catches RFC 1123 violations

kmock validates resource names against RFC 1123 (lowercase, hyphens, etc.) like real K8s. Fakes that skip this validation hide bugs (e.g., `app-A` accepted in test, rejected in prod). This is a feature: kmock's strictness here matches reality, unlike some lighter-weight fakes.

## Coverage and runtime envelope

The first integration test (`tests/integration/test_kmock_failure.py`) drives the cycle to a `FAILURE` verdict against a seeded broken cluster state. Coverage delta from this test alone: 65% → 74% (+9pp). End-to-end runtime: <1 second on the project's CI runner. Coverage hot spots reached by this test: `k8s_client.py` and `github_client.py` to 100%, `cycle.py` to 100%, `io_adapters.py` to 81%.

## When to reach for `envtest` instead

Per `ADR-020`, kmock is the chosen tool. `envtest` is the right fallback when:

- A test must exercise HTTPS-gated code paths in production.
- A test needs to validate against the real apiserver's strategic-merge-patch implementation (list-of-dicts in spec).
- A test must observe real K8s behaviors that kmock does not model (admission webhook chains, finalizer ordering, watch-event sequencing across multiple resources).

For scope inside the convergence-checker (CRD reads, flat-map ConfigMap PATCH, GitHub-as-stubbed-HTTP), kmock is the right choice and the quirks above are manageable.
