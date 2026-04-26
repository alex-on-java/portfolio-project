# PoC Evaluation: kmock as K8s API surrogate

Branch `poc/cc-kmock`. One integration test driving `cycle.run_cycle()`
to a FAILURE verdict against a fully in-process kmock server.

## Setup cost

- **Test code**: 165 LoC, single async test plus three helpers (PEM
  generator, kmock seeder, reader builder).
- **Scaffolding**: empty `tests/integration/__init__.py`; +5 lines in
  `pyproject.toml`.
- **Time to first passing run**: passed on first invocation.
- **No `src/` changes.**

## What worked out of the box

- Ephemeral-port allocation; parallel `pytest` processes both pass.
- In-memory state: PATCH reflects in next GET; LIST returns seeded
  items.
- CRD list endpoints once `kmock.resources` is populated with `kind` +
  `namespaced` — both namespaced and cluster-scoped work.
- PATCH content-type ambivalence: kmock parses body as JSON and
  type-dispatches (`Mapping → merge-patch`, `Sequence → JSON Patch`),
  so the SDK's strategic-merge content-type just works for flat
  `.data` ConfigMaps.

## Workarounds

| What | Why | What would make it unnecessary |
|---|---|---|
| `kmock==0.7.0` instead of `0.7` | conftest pinning rule requires `X.Y.Z`; PEP 440 normalizes both. | Loosen the regex, or upstream 3-segment releases. |
| `await asyncio.to_thread(cycle.run_cycle, …)` | kmock fixture is async; kubernetes SDK is sync — same loop deadlocks aiohttp. | A sync wrapper fixture in kmock (issue #24). |
| `# pylint: disable=duplicate-code` | Identical 9-line Stage `status` literal lives in `tests/test_models.py`. | Project-level disable for `tests/**`. |
| Pre-create `observability/*` ConfigMaps | `write_state`/`write_heartbeat` use PATCH; kmock 404s PATCH-of-missing. | None — faithful to real K8s. |
| In-test RSA generation via `cryptography` | PyJWT requires a real RSA key for `RS256`. | A `GitHubAppClient` test-double. |

## HTTPS / discovery / CRDs / state

- **HTTPS**: not supported. `http://` host + `verify_ssl=False`. Fine
  in-process; not OK if production code inspects `cfg.host`.
- **API discovery**: built-in. `/api`, `/apis`, `/api/v1`, group/version
  endpoints served from registered resources. SDK's per-group clients
  don't run a discovery prelude — partial registration suffices.
- **CRDs**: `kmock.resources['g/v/plural'] = {kind, namespaced, verbs}`.
  Cluster-scoped uses `namespace=None` in the object key tuple. No
  CRD-object parsing — pure metadata.
- **State**: in-memory KV. `resourceVersion` is the literal `"..."`
  (issue #33) — irrelevant here.

## Coverage

Baseline 65% → **74%** (+9 pp). One test brought `k8s_client.py`,
`github_client.py`, `cycle.py` to 100% and `io_adapters.py` to 81%.
Remaining gaps: `loop.py` (deliberately bypassed), `cli.py`,
`config.py`, `__main__.py`.

## Verdict

**Ship-it for the failure-mode PoC slot — conditionally.** Before
scaling beyond a single test:

1. Wrap the `asyncio.to_thread` bridge in a fixture; otherwise it
   becomes boilerplate.
2. Confirm no production path requires `https://`, or kmock is off
   the table.
3. v0 library: pin exactly, budget upgrade time per minor.
4. Strategic-merge semantics (list-of-dicts on Pod/Deployment specs)
   silently diverge — convergence-checker doesn't need them, other
   apps might.
5. Move RSA generation to a session-scoped fixture if more
   GitHub-touching tests land (~2s/test).

For convergence-checker's K8s + GitHub scope, kmock is fast
(sub-second), self-contained (no Docker, kubeconfig, FS state, fixed
port), and faithful enough. The async fixture is the biggest single
integration tax; everything else is modest seeding code.
