# CQP-007: Parallel-runnable checks avoid shared mutable generated state

**Rule:** Tests, linters, validators, hooks, and CI checks that can run in
parallel must not read and write shared mutable generated state unless that state
is immutable, isolated per run, or protected by an explicit synchronization
protocol.

**Why this matters:** Validation code is often executed in overlapping local
sessions, pre-commit hooks, CI jobs, and agent-driven verification loops. A check
that deletes or rewrites a shared generated directory can corrupt another check
that already handed paths from that directory to a downstream tool. The failure
then points at the downstream tool or the artifact being validated, even though
the real cause is shared mutable state in the validation runner.

Parallel safety is part of the correctness contract for the check. A check that is
green only when it runs alone is not reliable evidence. It can waste debugging
time, hide real regressions behind flaky infrastructure, and teach future
changes to normalize global cleanup as a validation pattern.

## Scope

The rule applies to repository checks that may be invoked by multiple terminals,
pre-commit processes, CI jobs, or agents at the same time:

- Pytest suites and fixtures
- Linters, formatters, validators, and policy runners
- Pre-commit hooks and local verification scripts
- CI scripts that generate intermediate files before invoking a tool
- Cache, render, schema, fixture, or report preparation used by those checks

The rule covers generated state, not every shared read. Reading immutable
committed files is fine. Reading a version-keyed cache is fine when cache
population is atomic or otherwise safe for concurrent readers. The risk appears
when one run can delete, rewrite, partially populate, or reinterpret a path that
another run is also using.

## Compliant Examples

- A pytest session creates generated CRD schemas under its own temporary
  directory and passes that directory to kubeconform. Separately, Kubernetes
  schema downloads remain in a version-keyed cache because they are not the
  per-run generated output.
- A validator writes rendered manifests to `tmp_path_factory.mktemp(...)` and
  passes the returned path through fixtures instead of rediscovering a stable
  workspace path.
- A CI job writes reports under a job-specific output directory keyed by the run
  identifier.
- A shared cache stores immutable artifacts by content digest or exact version,
  writes files atomically, and never deletes an artifact while readers may use
  it.
- A check that truly needs a single shared mutable resource uses an explicit
  lock or another synchronization protocol around the whole read/write critical
  section.

## Non-compliant Examples

- A pytest fixture deletes and recreates `.cache/generated-output/` while another
  pytest process may already be validating files from that directory.
- A pre-commit hook writes generated manifests to a stable workspace path and
  assumes no other hook or terminal is running the same command.
- A validator treats a global temporary directory as disposable and cleans it
  before each run without synchronizing with readers.
- A CI matrix job writes all shards' generated fixtures to the same mutable path
  and lets whichever shard finishes last define the final contents.
- A race fix commits sleeps, permanent race probes, debug prints, or bespoke
  verification code whose only purpose is proving that the race is absent.

## Exceptions

- **Immutable generated artifacts.** A shared path is acceptable when the
  artifact is addressed by content, exact version, or another immutable key, and
  writers use atomic publication.
- **Explicit synchronization.** A shared mutable path is acceptable when every
  reader and writer participates in the same lock or equivalent coordination
  mechanism.
- **Single-owner lifecycle.** A generated path owned by one long-running process
  can be acceptable when no supported workflow invokes another reader or writer
  concurrently.
- **Temporary implementation probes.** Sleeps, visible diagnostics, and manual
  race probes are allowed during local implementation when they are removed
  before commit.

## Review Heuristic

Ask what happens when two copies of the check start at nearly the same time. If
one run can delete, truncate, rewrite, or partially populate a path that the
other run may read, the design needs per-run state, immutable state, or
synchronization.

Then trace the path handoff. If a downstream tool receives a path to generated
state, that path should either be unique to the run or protected for the entire
time the downstream tool may read it.

## Sibling Enforcement

No automated check today. This policy is enforced during review of tests,
linters, hooks, CI scripts, and validation tooling changes.

When reviewing such a change, identify each generated output path and classify it
as per-run, immutable, synchronized, or unsafe. Require committed sleeps, debug
prints, and permanent race-only probes to be removed before merge.
