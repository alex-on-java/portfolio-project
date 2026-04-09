# Application Checks — Rollouts and Pods

Each environment (dev, stg, prd) is an independent namespace with identical structure.

## What Should Be Green

**Rollout** (`web-app` in each env namespace): phase must be `Healthy`.
- `availableReplicas` equals `replicas` (1)
- `stableRS` is set and equals `currentPodHash`
- No conditions with `status: False`

**Pods**: the running pod's image must match the image digest in the Kargo freight. An image matching
the previous promotion means the Rollout has not updated yet.

**Services**: both `web-app-active` and `web-app-preview` must exist in each namespace.
Both are ClusterIP on port 80. During normal steady state, both selectors point to the same ReplicaSet.

## Blue-Green Behavior

The Rollout uses blue-green strategy with `autoPromotionEnabled: true`. When a new image arrives:
1. A new ReplicaSet is created (preview)
2. `web-app-preview` service switches to the new ReplicaSet
3. Once the new pod is ready and auto-promotion fires, `web-app-active` switches
4. The old ReplicaSet scales down after 35 seconds

A Rollout in `Progressing` phase is healthy — it's mid-update. Only `Degraded` or `Paused`
(without an expected manual pause) needs investigation.

## Health Check Verification

Kargo runs an HTTP health check via a Job in the `portfolio-project` namespace after dev and stg
promotions. A completed Job means verification passed. A running Job means verification is in
progress. A failed Job means the health check timed out — the service was not reachable within
150 seconds (30 attempts × 5s).
