---
name: app-troubleshooting
description: |
  Diagnose application-level deployment issues.
  Use when a Rollout is stuck or degraded, pods are failing,
  health checks are timing out, or services are misconfigured.
user-invocable: false
---

## Architecture Context

Each environment (dev, stg, prd) is an independent namespace with identical structure.
The web-app runs as an Argo Rollout using Blue-Green strategy with two services:
`web-app-active` (stable traffic) and `web-app-preview` (new version during rollout).
Auto-promotion is enabled — manual intervention is not expected during normal operation.

## Diagnostic Approach

**1. What phase is the Rollout in?**
- `Healthy` — stable, no action needed
- `Progressing` — update in flight, normal, wait for it to settle
- `Degraded` — something failed; check conditions and events on the Rollout resource
- `Paused` — unexpected unless a manual pause was set

Check `status.conditions` for the specific failure reason before looking elsewhere.

**2. Are the pods running?**
A new ReplicaSet is created for each rollout update. If the new pod is not starting:
- `ImagePullBackOff` / `ErrImagePull`: the image digest does not exist in GHCR, or the
  imagePullSecret is missing or invalid
- `CrashLoopBackOff`: the container starts but crashes — check pod logs
- `Pending`: insufficient node resources or scheduling constraint

Check events on both the pod and the ReplicaSet.

**3. Is the readiness probe passing?**
The readiness probe is HTTP GET on port 3000 at `/`. If the pod starts but does not become ready:
- The nginx container serves static content and should respond immediately — a failing probe
  usually means the container crashed after starting or the port is wrong
- Check actual container logs for startup errors

**4. Is the Kargo health check failing?**
After dev or stg promotion, Kargo runs a Job in the `portfolio-project` namespace that curls
the active service URL (`http://{app}-active.{env}.svc.cluster.local/`):
- Job running: verification in progress, wait (up to 150 seconds total)
- Job failed: the curl could not reach the service — the pod may not be ready yet, DNS not
  propagated, or the service selector is wrong
- The health check runs via in-cluster DNS; no ingress or network policy is involved

**5. Are the services correct?**
Both `web-app-active` and `web-app-preview` must exist in each env namespace. During steady
state both point to the same ReplicaSet. During a rollout, `web-app-preview` temporarily points
to the new ReplicaSet. Check that selector labels match the current pod hash.

## Escape

`kubectl describe rollout web-app -n {env}` shows the full event history.
`kubectl get analysisrun -n portfolio-project` shows health check state and metrics.
Check pod logs directly for application-level errors.
