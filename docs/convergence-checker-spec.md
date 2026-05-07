# Convergence-Checker — Behavioural Specification

This document specifies the convergence-checker as a contract: the inputs it
observes, the decisions it makes, the side effects it produces, and the timing
guarantees it must meet. It is deliberately neutral about **how** the checker is
built — language, libraries, runtime form, deployment topology, and persistence
strategy are all rebuilder decisions.

Every observable value mentioned below originates in an external system —
Kubernetes API, the ArgoCD `Application` CR, the Kargo `Project`/`Stage` CRs,
the cluster-identity ConfigMap, or the GitHub commit-status API. No internal
verdict labels, sentinel constants, or implementation vocabulary appear.

---

## 1. Purpose

The checker exists to provide a **single GitHub commit status** that reflects
sustained convergence — or explicit failure — of the GitOps deployment that
follows ephemeral-cluster provisioning for a pull request. The status is a
required merge gate: until it reports `success`, the PR cannot be merged, and
its absence keeps the PR blocked.

The observable result is therefore a commit status posted against the PR's head
commit, transitioning between `pending`, `success`, and `failure` as the
cluster's ArgoCD Applications and Kargo Stages evolve.

---

## 2. External contracts

### 2.1 Cluster identity (input)

The checker reads a single ConfigMap that identifies which PR the cluster
belongs to and where ArgoCD lives. Both the namespace holding this ConfigMap
and the ConfigMap's name are inputs to the checker — they must not be
hardcoded.

Keys consumed from `.data`:

| Key                 | Type   | Required | Used for                                                                                     |
|---------------------|--------|----------|----------------------------------------------------------------------------------------------|
| `prCommitSha`       | string | optional | The commit SHA against which the GitHub status is posted. Absence disables status reporting. |
| `argocdNamespace`   | string | optional | The namespace where ArgoCD `Application` CRs are listed. Absence falls back to `argocd`.     |

All other keys present in this ConfigMap are ignored.

### 2.2 ArgoCD Applications (input)

The checker lists all `Application` custom resources (group `argoproj.io`,
version `v1alpha1`, plural `applications`) in the namespace given by
`argocdNamespace`. The set is discovered at runtime — there is no hardcoded
application name, label selector, or filter.

Fields consumed per Application:

| Path                          | Type   | Used for                                       |
|-------------------------------|--------|------------------------------------------------|
| `.metadata.name`              | string | Identification in status descriptions.         |
| `.status.health.status`       | string | Per-Application health classification.         |
| `.status.sync.status`         | string | Per-Application sync classification.           |
| `.status.operationState.phase`| string | Per-Application operation outcome.             |

Values these fields can hold (only the values listed below influence a
decision; any other observed value is treated as not-yet-converged):

- `.status.health.status`: `Healthy`, `Degraded`, plus any other value
  (e.g. `Progressing`, `Suspended`, `Missing`, `Unknown`, or absent).
- `.status.sync.status`: `Synced`, plus any other value (e.g. `OutOfSync`,
  `Unknown`, or absent).
- `.status.operationState.phase`: `Failed`, `Error`, plus any other value
  (e.g. `Succeeded`, `Running`, `Terminating`, or absent).

Fields deliberately ignored:

- `.status.conditions` — observed to be `null` on every Application in the
  live cluster. A rebuilder might reasonably expect this to carry sync errors;
  it does not, so reading it adds no decision power.
- `.status.resources`, `.status.history`, `.status.summary`, and all other
  fields not in the table above.

### 2.3 Kargo Stages (input)

Stages are namespaced. Their namespaces are discovered indirectly: the checker
lists every `Project` CR (group `kargo.akuity.io`, version `v1alpha1`, plural
`projects`, cluster-scoped) and uses each Project's `.metadata.name` as a
namespace name. It then lists `Stage` CRs (same group/version, plural `stages`)
in each such namespace. There is no hardcoded namespace list, and no direct
namespace lookup independent of the Project CRs.

Fields consumed per Stage:

| Path                          | Type    | Used for                                       |
|-------------------------------|---------|------------------------------------------------|
| `.metadata.name`              | string  | Identification in status descriptions.         |
| `.metadata.namespace`         | string  | Identification in status descriptions.         |
| `.status.health.status`       | string  | Per-Stage health classification.               |
| `.status.conditions[]`        | array   | Per-Stage condition classification (see below).|

From the conditions array, the checker extracts only entries whose `type` is a
string and whose `status` is exactly `"True"` or `"False"`. Other entries are
ignored. Three condition types influence decisions:

- `type: Healthy`, `status: True` / `False`
- `type: Ready`, `status: True` / `False`
- `type: Verified`, `status: True` / `False`

Values `.status.health.status` can hold that influence decisions:

- `Healthy`, `Unhealthy`, plus any other value (e.g. `Progressing`, `Unknown`,
  or absent).

Fields deliberately ignored:

- `.status.phase` — observed to be `null` on every live Stage. A rebuilder
  reading Kargo documentation might expect a phase enum; the live API does not
  populate it.
- `.status.health.issues`, condition `lastTransitionTime`, `reason`, `message`,
  `observedGeneration`, and all other fields not in the table above.

### 2.4 Heartbeat ConfigMap (output to in-cluster watchdog)

The checker writes a ConfigMap in its own namespace that signals it is alive.
The ConfigMap's name and namespace are inputs (the namespace is the namespace
the checker itself runs in; the name is configured).

Each evaluation produces at most one write to a single key:

- `last-success`: ISO 8601 timestamp (with timezone, microsecond precision is
  acceptable) no older than the evaluation that produced it.

The write uses Server-Side Apply with a stable field-manager identifier, so
that cooperating writers do not conflict.

The ConfigMap is consumed by a separate watchdog component. The watchdog's
logic, schedule, and thresholds are out of scope for this spec — the contract
between checker and watchdog is the freshness of `last-success` and nothing
more.

### 2.5 GitHub commit-status API (output)

The checker posts to GitHub via the commit-status REST API
(`POST /repos/{owner}/{repo}/statuses/{sha}`).

| Field         | Value                                                                         |
|---------------|-------------------------------------------------------------------------------|
| `owner/repo`  | Configured at deployment time (currently `alex-on-java/portfolio-project`).    |
| `sha`         | The value of `prCommitSha` from the cluster-identity ConfigMap.               |
| `context`     | The literal string **`GitOps Convergence Gate`**. This must not change.       |
| `state`       | One of `pending`, `success`, `failure`. `error` is not used.                  |
| `description` | A human-readable string, truncated to 140 characters before posting.          |
| `target_url`  | Not sent.                                                                     |

The context string is a hard contract: the repository's branch ruleset for the
default branch lists exactly this string in `required_status_checks`, alongside
`build / build`, `dispatch-pr-push`, `Ephemeral Cluster`, and `Ephemeral DNS`.
Any deviation in spelling, casing, or whitespace makes the rebuilt checker
inert as a merge gate.

The same context is also written by the separate watchdog component when the
checker itself stops heartbeating; this spec does not specify watchdog
behaviour, only that the context name is shared and therefore must remain
stable.

---

## 3. Decision logic

The checker classifies each observed resource individually, then aggregates the
classifications into a single verdict per evaluation. An *evaluation* is the
unit of work this contract is written against: each evaluation produces (a) a
verdict for the cluster's current state, (b) at most one GitHub commit-status
post (subject to dedup, §4.1), and (c) at most one heartbeat write (§4.3).
The contract specifies what each evaluation must produce; the trigger
mechanism for evaluations is out of scope.

### 3.1 Per-Application classification

Given an Application `A`, evaluate the rules **in order** and stop at the first
match:

1. If `A.status.health.status == "Degraded"` → **broken**.
2. If `A.status.operationState.phase` is one of `Failed`, `Error` → **broken**.
3. If `A.status.health.status == "Healthy"` **and** `A.status.sync.status == "Synced"` → **converged**.
4. Otherwise → **in-progress**.

Notes:

- A missing `.status` block, or any of its sub-objects, never throws. The
  classifier treats absent fields as "neither match", which falls through to
  rule 4 (in-progress).
- "Degraded" takes precedence over the operation-phase failure check, but both
  are equally broken from the verdict's perspective; the ordering only
  determines which value appears in the human description.

### 3.2 Per-Stage classification

Given a Stage `S`, with `cond[T]` denoting the boolean derived from the
condition entry of `type T` (`true` if its `status == "True"`, `false` if
`"False"`, undefined if absent), evaluate **in order** and stop at the first
match:

1. If `S.status.health.status == "Unhealthy"` → **broken**.
2. If `cond[Healthy] == false` → **broken**.
3. If `S.status.health.status == "Healthy"` **and** `cond[Ready] == true`
   **and** `cond[Verified] == true` → **converged**.
4. Otherwise → **in-progress**.

Notes:

- Rules 1 and 2 are independent: a Stage can be classified as broken via either
  path. Rule 1 fires when Kargo's aggregated health enum says so; rule 2 fires
  when the explicit `Healthy` condition is `False`, which in practice may
  appear before or independently of the aggregate enum.
- Rule 3 requires **all three** conditions to be `True`. A Stage with
  `health.status == "Healthy"` but missing or `False` `Ready`/`Verified`
  conditions falls through to in-progress.

### 3.3 Aggregation across resources within one evaluation

Let `R` be the set of all per-resource classifications produced in a single
evaluation (Applications and Stages combined).

1. **Any broken → broken.** If any element of `R` is broken, the evaluation's
   classification is broken. The aggregated description lists each broken
   resource with the value that triggered its classification.

2. **All converged → candidate-converged.** If every element of `R` is
   converged **and** `R` is non-empty, the evaluation is a candidate for
   converged (subject to the stability window in §3.4).

3. **Otherwise → in-progress.** Some resources are converged but not all, and
   none are broken.

If `R` is empty (no Applications, no Stages discovered), the evaluation is
treated as candidate-converged: the consecutive-converged counter advances and
the in-progress timer is cleared exactly as if every resource had been
converged. (Whether this is desirable for an empty cluster is a known
divergence; see §8.)

### 3.4 Aggregation across time (stability window)

A single observation of all-converged is never sufficient to report `success`.
The checker maintains a **consecutive-converged counter** across evaluations:

- On every broken evaluation, the counter resets to zero.
- On every in-progress evaluation, the counter resets to zero.
- On every candidate-converged evaluation, the counter increments by 1, capped
  at `2 × stability_threshold` to prevent unbounded growth.

The evaluation's reported verdict is:

- **broken** — if the evaluation is broken (immediate, no stability
  requirement).
- **converged** — if the evaluation is candidate-converged **and** the counter
  has reached `stability_threshold`.
- **in-progress** — in every other case, including candidate-converged
  evaluations that have not yet reached the threshold.

The default `stability_threshold` is **5**, and the default minimum
re-evaluation period is **12 seconds**, giving a minimum sustained-convergence
window of roughly **60 seconds** before `success` is reported. Both values are
configurable inputs.

### 3.5 Safety timeout (in-progress escalates to broken)

The checker also tracks the timestamp at which it first observed an
in-progress evaluation (i.e. the first evaluation where some resources were
not converged but none were broken). This timestamp is preserved across
successive in-progress evaluations.

If the elapsed wall-clock time since this timestamp is **strictly greater
than** `safety_timeout_seconds` (default **900 seconds**, configurable), the
evaluation's verdict is escalated from in-progress to broken. The escalation's
description identifies the resources still in-progress and states that the
safety timeout was exceeded.

The timestamp is cleared (back to "not currently in-progress") whenever:

- An evaluation reports broken (the counter is also reset).
- An evaluation is candidate-converged (regardless of whether the threshold
  has been reached — being on a converged trajectory clears the timer).

A subsequent in-progress evaluation will then start the timer afresh.

### 3.6 PR-commit-SHA change

The cluster-identity ConfigMap can change between evaluations (e.g. the same
ephemeral cluster being repurposed for a new commit on the same PR, or a
testing scenario). On every evaluation, the checker compares the current
`prCommitSha` against the value seen in the previous evaluation. If they
differ:

- The consecutive-converged counter resets to zero.
- The first-in-progress timestamp is cleared.
- The "last-posted (state, description)" memory is cleared, so the first
  status of the new SHA is always sent (no spurious dedup against the previous
  SHA's last value).

If `prCommitSha` is absent from the ConfigMap, the checker continues to
evaluate but does not post any GitHub status (see §4.1).

---

## 4. Side effects

### 4.1 GitHub status posting — trigger and dedup rules

After computing the evaluation's verdict, the checker maps it to a GitHub
state:

| Evaluation verdict | GitHub `state` |
|--------------------|----------------|
| broken             | `failure`      |
| in-progress        | `pending`      |
| converged          | `success`      |

It then constructs a `(state, description)` tuple and compares it to the last
tuple it posted for the current `prCommitSha`. It posts to GitHub only when:

- `prCommitSha` is present (non-empty), **and**
- the new tuple differs from the last posted tuple for this SHA.

Otherwise the post is skipped. This deduplication keeps the PR's status
history readable when nothing material has changed (e.g. once the
converged-counter has hit its cap and the description stops changing).

If the GitHub API call raises, the failure is logged and the previously
remembered tuple is preserved unchanged — i.e. the next evaluation will retry
the same post.

### 4.2 Description format

Descriptions are truncated to a maximum of 140 Unicode codepoints at the
boundary with the GitHub API. The truncation is a hard slice — no ellipsis,
no smart-break on word boundaries. The pre-truncation forms below are the
contract; truncation is purely a defensive measure.

| Verdict / situation                                   | Description pattern                                                                                  |
|-------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| Broken — one or more broken resources                 | `Failed: <r1 desc>; <r2 desc>; ...` where each `<r desc>` follows the per-resource rules below.      |
| Broken — safety timeout exceeded                      | `Safety timeout (<seconds>s) exceeded. Pending: <r1 desc>; <r2 desc>; ...`                           |
| In-progress — some resources still in-progress        | `<N> resources pending` (where `<N>` is the count of in-progress resources)                          |
| In-progress — all converged but threshold not reached | `Healthy <count>/<threshold> — awaiting stability`                                                   |
| Converged — threshold reached                         | `All <total> resources healthy for <count> consecutive checks`                                       |

Per-resource description fragments (used inside aggregated descriptions):

- Application classified as broken via `health.status == "Degraded"`:
  `<name>: Degraded`
- Application classified as broken via operation phase:
  `<name>: operation Failed` or `<name>: operation Error`
- Application classified as converged: `<name>: Healthy+Synced`
- Application classified as in-progress:
  `<name>: health=<value> sync=<value> op=<value>`
- Stage classified as broken via aggregate health: `<ns>/<name>: Unhealthy`
- Stage classified as broken via condition: `<ns>/<name>: Healthy condition is False`
- Stage classified as converged: `<ns>/<name>: Healthy+Ready+Verified`
- Stage classified as in-progress:
  `<ns>/<name>: health=<value> ready=<bool-or-null> verified=<bool-or-null>`

The literal token strings that originate in external systems (`Healthy`,
`Synced`, `Degraded`, `Failed`, `Error`, `Unhealthy`) appear verbatim in
descriptions. The connector words (`for`, `consecutive checks`, `awaiting
stability`, `Pending`, `pending`, `resources`, `Failed:`) are conventions of
the description format, not external values.

### 4.3 Heartbeat write — trigger conditions

Each evaluation produces at most one heartbeat write. The write happens
regardless of:

- whether the evaluation's verdict was broken, in-progress, or converged;
- whether a GitHub post was sent or skipped;
- whether the GitHub post raised.

The write may happen before or after the GitHub post — the contract is
solely that the heartbeat key reflects an evaluation no older than the
evaluation that produced it.

If the heartbeat write itself raises, the failure is logged and the
evaluation moves on. (A persistently failing heartbeat is the watchdog's
signal to take over; the checker does not self-heal.)

---

## 5. Cadence and timing

| Parameter                                       | Default      | Configurable | Role                                                                                            |
|-------------------------------------------------|--------------|--------------|-------------------------------------------------------------------------------------------------|
| Minimum re-evaluation period                    | 12 s         | yes          | Minimum elapsed time between the start of one evaluation and the start of the next.             |
| Stability threshold (consecutive evaluations)   | 5            | yes          | Number of consecutive candidate-converged evaluations required before reporting `success`.      |
| Safety timeout                                  | 900 s        | yes          | Maximum continuous in-progress time before escalating to `failure`.                             |
| Counter cap                                     | 2× threshold | derived      | Upper bound on the consecutive-converged counter.                                               |
| GitHub description max length                   | 140          | no           | Truncation point at the GitHub API boundary.                                                    |

There are no input freshness/staleness rules: each evaluation reads the live
cluster state. The cluster-identity ConfigMap is re-read on every evaluation
(so SHA changes take effect on the next evaluation), and the heartbeat is
written on every evaluation (so its freshness is bounded by the re-evaluation
period plus single-evaluation latency).

There is no startup grace period: the first evaluation participates in the
stability window with no special handling.

---

## 6. State carried across evaluations

The checker carries a small amount of state from one evaluation to the next.
The contract does **not** require this state to survive restarts of the
checker: loss is bounded as follows, and a rebuilder is free to persist
externally if they want stronger guarantees.

- The consecutive-converged counter restarting at zero only delays a `success`
  by `stability_threshold × re-evaluation period` seconds.
- The first-in-progress timestamp restarting only delays a safety-timeout
  escalation by at most `safety_timeout_seconds`.
- The last-posted `(state, description)` memory restarting causes at most one
  duplicate post per restart, which is harmless.

State items:

| Item                              | Reset triggers                                                                                       |
|-----------------------------------|------------------------------------------------------------------------------------------------------|
| Consecutive-converged counter     | Any broken or in-progress evaluation; PR-commit-SHA change.                                          |
| First-in-progress timestamp       | Any broken or candidate-converged evaluation; PR-commit-SHA change.                                  |
| Last-posted (state, description)  | PR-commit-SHA change.                                                                                |
| Last-seen `prCommitSha`           | Used for change detection; updated on every evaluation to whatever the ConfigMap currently says.     |

---

## 7. Failure modes

The checker must remain a useful merge gate even when something goes wrong.
The required externally-observable behaviours are:

| Failure                                              | Required behaviour                                                                                                                                   |
|------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|
| Cluster-identity ConfigMap unreadable                | The evaluation is logged and skipped; no GitHub post is made for this evaluation. Whether a heartbeat write occurs is implementation-defined (it depends on whether the heartbeat write was sequenced before the failed read). |
| Cluster-identity ConfigMap missing `prCommitSha`     | Evaluations continue, but no GitHub post is attempted. Heartbeat continues to be written.                                                            |
| Listing Applications, Projects, or Stages fails      | The evaluation is logged and skipped. State is not advanced. The next evaluation retries from scratch.                                                |
| Some Applications return malformed `.status` blocks  | They classify as in-progress (rule 4 of §3.1). The evaluation proceeds with the rest of the resources.                                               |
| GitHub API call fails (timeout, 5xx, auth error)     | The error is logged. The remembered "last-posted" tuple is **not** updated, so the next evaluation retries the same post. State and counters advance normally. |
| Heartbeat write fails                                | The error is logged. The evaluation continues. Persistent failure leaves the watchdog's input (`last-success`) stale; what the watchdog does with that is its own contract. |
| Checker stops producing GitHub posts entirely (for any reason) | No new `GitOps Convergence Gate` status appears on the PR. Because branch-ruleset enforcement requires that exact context, **merge is blocked**. |
| Inconsistent inputs (e.g. partially-populated Stage) | The classifier's "fall through to in-progress" semantics ensure no crash; the resource is treated as not-yet-converged.                              |

The recurring principle is **fail closed**: every failure either keeps the
status `pending`/missing or escalates to `failure`. There is no path that can
produce a `success` from a degraded checker.

---

## 8. Credentials and permissions

### 8.1 Kubernetes API

The checker must be able to:

| Verb        | Resource                                                  | Scope                                |
|-------------|-----------------------------------------------------------|--------------------------------------|
| `get, list` | `applications.argoproj.io`                                 | The ArgoCD namespace (from §2.1).    |
| `get, list` | `projects.kargo.akuity.io`                                 | Cluster-wide (Projects are cluster-scoped). |
| `get, list` | `stages.kargo.akuity.io`                                   | Each namespace named after a Project. |
| `get`       | The cluster-identity ConfigMap                             | Its specific namespace and name only. |
| `patch`     | The heartbeat ConfigMap                                    | Its specific namespace and name only. |

Why the scoping matters: the checker is in-cluster code, but its blast radius
on credential exposure should be a strict subset of "read application status".
Cluster-wide list on Projects is unavoidable (Projects are cluster-scoped);
cluster-wide list on Stages is **not** required and must not be granted —
namespaced list per discovered Project is sufficient. ConfigMap permissions
are pinned to specific resource names with `resourceNames` on the Role to
prevent the checker from reading or writing other ConfigMaps in the same
namespace.

### 8.2 GitHub

The checker authenticates to GitHub as a **dedicated GitHub App**, distinct
from any broader-scoped App used elsewhere by the project. Its installation
must grant exactly:

- **Commit statuses: write** on the PR's repository.

It must not be granted Contents, Pull requests, Checks, Workflows,
Administration, or any other permission. The credential lives inside the
ephemeral cluster as a Kubernetes Secret; minimal scope bounds the impact of
exposure.

The mechanism is GitHub App installation tokens (signed JWT exchanged for an
installation access token). Tokens must be refreshed before they expire; a
token cached for less than its issued lifetime is acceptable.

---

## 9. Discovery: what is and is not dynamic

The checker's evaluation set is rebuilt on every evaluation. Specifically:

- Applications: every `Application` CR currently in the ArgoCD namespace.
- Stages: every `Stage` CR in every namespace named by a current `Project` CR.

There is no:

- Hardcoded application name list.
- Hardcoded stage name list.
- Hardcoded namespace list (other than the configured names of the
  cluster-identity ConfigMap and the checker's own heartbeat ConfigMap).
- Label selector or annotation filter narrowing the evaluation set.

Adding a new ApplicationSet, a new Kargo Project, or a new Stage to the
cluster requires **zero changes** to the checker.

---

## 10. Configuration surface

The checker takes the following configuration inputs. All defaults are
contractual — a rebuilder choosing different defaults is choosing different
behaviour.

| Input                                  | Default                              | Notes                                                                          |
|----------------------------------------|--------------------------------------|--------------------------------------------------------------------------------|
| Minimum re-evaluation period (seconds) | 12                                   | See §5.                                                                        |
| Stability threshold (consecutive evaluations) | 5                             | See §3.4.                                                                      |
| Safety timeout (seconds)               | 900                                  | See §3.5.                                                                      |
| GitHub status context                  | `GitOps Convergence Gate`            | Must match branch-ruleset; do not parameterise without coordinating both ends. |
| GitHub `owner/repo`                    | `alex-on-java/portfolio-project`     | Where statuses are posted.                                                     |
| Cluster-identity namespace             | (configured at deploy time; today: `kargo-shared-resources`) | No fallback.                                       |
| Cluster-identity ConfigMap name        | (configured at deploy time; today: `cluster-identity`)       | No fallback.                                       |
| ArgoCD namespace fallback              | `argocd`                             | Used when `argocdNamespace` key is absent from the cluster-identity ConfigMap. |
| Heartbeat ConfigMap name               | (configured at deploy time; today: `gitops-convergence-heartbeat`) | Lives in the checker's own namespace.       |
| Field-manager identifier               | (configured at deploy time)          | Used as the SSA field-manager when patching the heartbeat ConfigMap.            |

GitHub App credentials (`app id`, `private key`, `installation id`) are
required inputs. Absence of any of the three disables GitHub posting entirely
(the checker continues to evaluate and write heartbeats). The transport
mechanism for delivering these inputs to the checker is a deployment decision.

---

## 11. Test obligations on the rebuild

These are not implementation hints — they are decision points that any rebuild
must demonstrably handle. Each is statable as a unit or integration test
without consulting any code.

1. An Application with `health.status == "Degraded"` produces a broken
   classification on the next evaluation, regardless of `sync.status` or
   `operationState.phase`.
2. An Application with `operationState.phase == "Failed"` (or `"Error"`)
   classifies as broken even if `health.status == "Healthy"`.
3. A Stage with `health.status == "Healthy"`, `cond[Ready] == true`, and
   `cond[Verified] == true` classifies as converged. Removing any one of the
   three drops it to in-progress (unless `cond[Healthy]` is `false`, which
   makes it broken).
4. An evaluation in which all `N` resources classify as converged does **not**
   post `success` on its first occurrence; it must be observed
   `stability_threshold` times consecutively first.
5. A single broken resource appearing during the stability window resets the
   counter — a subsequent return to all-converged restarts the count from 1.
6. An in-progress condition lasting (strictly) longer than
   `safety_timeout_seconds` of wall-clock time produces a `failure` post whose
   description names the still-in-progress resources.
7. A change in `prCommitSha` between evaluations wipes the counter, the timer,
   and the last-posted memory.
8. The same `(state, description)` is not posted twice in a row for the same
   `prCommitSha`.
9. With `prCommitSha` absent, no GitHub post is attempted, but heartbeats
   continue.
10. A failure of the GitHub API call leaves the last-posted memory unchanged
    so the next evaluation retries.

---

## 12. Out of scope (reaffirmed)

- DNS availability and HTTPS reachability of deployed workloads.
- Per-application or per-stage Check Runs (the contract is one aggregated
  status).
- ArgoCD Notifications.
- Permanent (non-ephemeral) cluster monitoring.
- The behaviour of the watchdog component (only its contract surface — the
  heartbeat ConfigMap key and the shared status context name — is specified
  here).
- The behaviour of the cluster-identity producer (only the keys consumed
  appear above).

---

## Appendix: Known divergences

These are observed behaviours in the live cluster that diverge from
documentation, charter intent, or what a rebuilder might naively expect from
the public APIs of ArgoCD, Kargo, GitHub, or Kubernetes. They are recorded as
data points, not recommendations — a rebuild may close any of them
deliberately.

1. **ArgoCD `.status.conditions` is excluded because it is empty.** Across all
   15 Applications observed in the live cluster, `.status.conditions` is
   `null`. The contract therefore excludes `.status.conditions` from the
   field set; `health.status`, `sync.status`, and `operationState.phase` carry
   the signal a rebuilder might otherwise expect from conditions. If a future
   ArgoCD version begins populating `.status.conditions`, reading it should be
   reconsidered.

2. **Kargo `.status.phase` is excluded because it is empty.** Kargo
   documentation references a phase enum on Stages; the live cluster shows
   `null` on every Stage. The contract uses `.status.health.status` and the
   conditions array instead. This is a known reality-vs-docs gap in the Kargo
   API.

3. **Kargo Warehouses are outside the evaluation set.** Warehouses are present
   in the live cluster as a Kargo concept that sits alongside Applications and
   Stages, but the contract's evaluation set comprises only Applications and
   Stages. A rebuilder choosing to extend the contract to include Warehouses
   would change observable behaviour and should treat the change as a
   contract revision, not a fix.

4. **The verdict is not commit-bound at the resource level.** The contract
   classifies whichever Applications and Stages are currently in the cluster;
   it does not require verifying that each resource's observed revision
   matches `prCommitSha`. This means a Stage that has not yet rolled forward
   to the PR's commit can still classify as converged. The stability window
   and safety timeout are the only time-domain protections against this — a
   per-resource revision watermark is not part of the current contract.

5. **An empty evaluation set is treated as candidate-converged.** If the
   checker is asked to evaluate a cluster with zero Applications and zero
   Stages, it advances the consecutive-converged counter and eventually posts
   `success`. This is unlikely in practice (every ephemeral cluster has at
   minimum a bootstrap Application), but it is a corner case worth noting.

6. **The `target_url` field on commit statuses is never populated.** The
   GitHub status currently has no link back to the checker's logs or
   dashboard. Branch-ruleset enforcement does not require it, but a rebuilder
   may choose to populate it for debuggability.

7. **The shared status context with the watchdog is implicit.** The watchdog
   posts `failure` on the same `GitOps Convergence Gate` context when it
   detects a stale heartbeat. From the GitHub side this is indistinguishable
   from a failure posted by the checker itself. This is intentional (a single
   merge gate), but it means GitHub status history alone cannot tell you which
   component made any given post.

8. **Branch protection is enforced via repository rulesets, not the legacy
   branch-protection API.** A rebuilder verifying the contract via the
   `/branches/{branch}/protection` endpoint will see "Branch not protected" —
   the required-status-checks list lives at `/repos/.../rules/branches/master`
   under a `required_status_checks` rule.
