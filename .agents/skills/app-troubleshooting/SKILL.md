---
name: app-troubleshooting
description: |
  Diagnose application-level deployment issues.
  Use when a Rollout is stuck or degraded, pods are failing,
  health checks are timing out, or services are misconfigured.
user-invocable: false
---

## Architecture Context

Every workload in the cluster is a set of pods under a controller (Deployment, StatefulSet,
Rollout, ...). The diagnostic playbook is mostly shared across controller types — the question is
always "why isn't the desired state the actual state?" Two workload classes deserve named
patterns in this cluster:

- **Rollouts (Argo Rollouts)** — blue-green or canary controller with verification gates.
  Phase enum: `Healthy` / `Progressing` / `Degraded` / `Paused`. Controller-specific diagnosis is
  `status.conditions` on the Rollout and any linked `AnalysisRun` (Kargo verification gate).
- **In-cluster gate reporters** — a Deployment whose job is to evaluate cluster state and post a
  GitHub commit status. Its failure modes differ from a generic workload because it participates
  in the PR merge gate (see `pr-verification` for the three-owner lifecycle). Today one instance
  runs (convergence-checker in `observability`); the pattern generalizes.

Discover workloads at runtime; don't assume names:

```
kubectl --context <ctx> get rollouts -A
kubectl --context <ctx> get deploy,statefulset -A
```

## Diagnostic Approach

**1. Which controller? What does its status say?**
Start with the top-level resource and read `status`:

```
kubectl --context <ctx> describe rollout -n <ns> <name>       # Rollout class
kubectl --context <ctx> get deploy -n <ns> <name> -o yaml     # Deployment class
```

`status.conditions` + `status.phase` (Rollout) or `status.conditions` (Deployment) answer: is
the controller itself blocked, or waiting on pods?

**2. Are pods running?**
Common blockers:
- `ImagePullBackOff` / `ErrImagePull` — image digest missing from registry, or `imagePullSecret`
  missing/invalid.
- `CrashLoopBackOff` — container crashes after start. `kubectl logs --previous` is the first move.
- `Pending` — node resources or scheduling constraint. `kubectl describe pod` + events on pod and
  controller.

**3. Is the readiness probe passing?**
The probe is the handoff from "started" to "receives traffic." A pod that runs but never becomes
Ready usually has an app-config or port mismatch — check the probe spec against the container's
actual listening address and compare container logs for startup errors.

**4. (Rollout class) Is verification blocking?**
Rollouts integrate with Kargo verification. A failed `AnalysisRun` pauses the Rollout. Discover
active runs, then inspect per-metric status:

```
kubectl --context <ctx> get analysisrun -A
kubectl --context <ctx> describe analysisrun -n <ns> <name>
```

The failing metric's status explains what the check observed (curl timeout, non-2xx, etc.).

### Gate-reporter-specific steps

**5. Silence diagnosis**
A reporter's job is to *report* — a silent reporter = a stuck gate. Silence causes:
- Pod not yet Ready (image pull, readiness probe, RBAC binding for the cluster-state reads the
  reporter performs).
- Pod crashing (Secret import errors, ConfigMap read errors). `CrashLoopBackOff` is visible;
  an outer `try/except` that swallows per-iteration exceptions is not — look at the structured
  log stream for an iteration-error event.
- GitHub auth failing (401 / 404 / 422 on status POST). The reporter's Secret (GitHub App
  credentials) has specific key names and a PEM-format private key — check that all expected keys
  exist before inspecting values.
- RBAC shortfall for dynamic discovery. Reporters that list cluster-wide resources (Applications,
  Stages, Projects) need ClusterRole-level read; a restrictive RoleBinding produces silent
  undercount rather than an error.

**6. Own-ConfigMap reconcile fight**
Reporters commonly write heartbeat and state into ConfigMaps that the same ArgoCD Application
also declares. Without `ignoreDifferences` on the written field (typically `/data`), ArgoCD
reverts the writes every sync — heartbeats thrash, the watchdog sees stale heartbeat, gate goes
`failure`. Cross-reference: `argocd-troubleshooting` for the pattern; fix is always an
`ignoreDifferences` block on the Application.

**7. Structured logs are the primary signal**
Reporters emit JSON via a structured-logging library. The event key is reporter-specific —
discover the schema first:

```
kubectl --context <ctx> logs -n <ns> deploy/<reporter> | head -1 | jq 'keys'
```

Then distribute events by name to find anomalies:

```
kubectl --context <ctx> logs -n <ns> deploy/<reporter> \
  | jq -r '.<event-key>' | sort | uniq -c | sort -rn
```

**8. Watchdog cross-check**
If the reporter is silent and you're trying to decide whether the reporter or its infrastructure
is at fault, see `cluster-troubleshooting` for the watchdog's liveness role. Reporter silent +
watchdog silent = infra gap (backstop unarmed). Reporter silent + watchdog firing = expected
behavior, focus on the reporter.

## Escape

`kubectl --context <ctx> describe <resource>` for full event history. Pod logs directly for
application-level errors. For reporter-class workloads,
`kubectl --context <ctx> get events -n <ns>` scoped to the reporter's pod.
