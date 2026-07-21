# CQP-007: Parallel-runnable checks avoid shared mutable generated state

**Rule:** Tests, linters, validators, hooks, and CI checks that can run in parallel must not read and write shared mutable generated state. Generated state that a check depends on must be isolated per run, immutable, or protected by an explicit synchronization protocol.

**Why this matters:** Validation code runs in overlapping local sessions, pre-commit hooks, CI jobs, and agent-driven verification loops. A check that deletes or rewrites a shared generated directory can corrupt another check that already handed paths from that directory to a downstream tool, and the resulting failure blames the downstream tool or the artifact under validation while the real cause sits in the validation runner.

Parallel safety belongs to the check's correctness contract. A run that passes only because nothing else happened to be running at the time wastes debugging effort on phantom failures, hides real regressions behind infrastructure noise, and leaves global cleanup in the tree as an example the next check will copy.

## Scope

The rule applies to repository checks that multiple terminals, pre-commit processes, CI jobs, or agents may invoke at the same time:

- Pytest suites and fixtures
- Linters, formatters, validators, and policy runners
- Pre-commit hooks and local verification scripts
- CI scripts that generate intermediate files before invoking a tool
- Cache, render, schema, fixture, or report preparation used by those checks

Only generated state falls under the rule. Reading immutable committed files is safe, and so is a version-keyed cache whose population is atomic or otherwise safe for concurrent readers. The risk appears when one run can delete, truncate, rewrite, partially populate, or reinterpret a path that another run is also using.

## Compliant examples

- ✓ A pytest session creates generated CRD schemas under its own temporary directory and passes that directory to kubeconform, while Kubernetes schema downloads stay in a version-keyed cache because they are not per-run output.
- ✓ A validator writes rendered manifests to `tmp_path_factory.mktemp(...)` and passes the returned path through fixtures instead of rediscovering a stable workspace path.
- ✓ A CI job writes reports under a job-specific output directory keyed by the run identifier.
- ✓ A shared cache stores immutable artifacts by content digest or exact version, writes files atomically, and never deletes an artifact while readers may use it.
- ✓ A check that truly needs a single shared mutable resource uses an explicit lock or another synchronization protocol around the whole read/write critical section.

## Non-compliant examples

- ✗ A pytest fixture deletes and recreates `.cache/generated-output/` while another pytest process may already be validating files from that directory.
- ✗ A pre-commit hook writes generated manifests to a stable workspace path and assumes no other hook or terminal is running the same command.
- ✗ A validator treats a global temporary directory as disposable and cleans it before each run without synchronizing with readers.
- ✗ A CI matrix job writes all shards' generated fixtures to the same mutable path and lets whichever shard finishes last define the final contents.

## Exceptions

- **Immutable generated artifacts.** A shared path is acceptable when the artifact is addressed by content, exact version, or another immutable key, and writers use atomic publication.
- **Explicit synchronization.** A shared mutable path is acceptable when every reader and writer participates in the same lock or equivalent coordination mechanism.
- **Single-owner lifecycle.** A generated path owned by one long-running process can be acceptable when no supported workflow invokes another reader or writer concurrently.

## Review heuristic

Reason through two copies of the check starting at nearly the same time. If either copy can disturb a path the other may read (any of the operations listed under *Scope*), the design needs per-run state, immutable state, or synchronization. Every path handed to a downstream tool deserves the same trace: it should stay valid for the whole window in which the tool may read it, either because the path is unique to the run or because the synchronization protocol covers that window.

## Sibling enforcement

No automated check today. This policy is enforced during review of tests, linters, hooks, CI scripts, and validation tooling changes; when reviewing such a change, classify each generated output path as per-run, immutable, synchronized, or unsafe.

A related review point: fixing a violation often involves sleeps, race-timing probes, or debug prints that exist only to demonstrate the race. That scaffolding is fair game during the implementation session and must be gone before merge. Committing it is a *Workarounds Are Broken Windows* concern rather than a violation of this rule, and it is noted here because reviews of parallel-safety fixes are where it keeps appearing.
