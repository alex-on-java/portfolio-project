# LL-0002: GKE NAP Invisible Resource Defaults and Warden Minimums

**Summary**: GKE Node Auto-Provisioning (NAP) applies 500m CPU / 2Gi memory defaults to pods without explicit resource requests, and Warden enforces Autopilot-style minimums (50m CPU / 52Mi memory) even on Standard clusters with NAP enabled.

## What happened

Operator pods (Kargo, cert-manager, argo-rollouts) were consuming far more node resources than expected despite light actual usage. The Helm charts for all three operators default to `resources: {}` (empty), meaning no resource requests are set.

## Root cause

Two independent GKE mechanisms interact:

1. NAP applies its own defaults (500m CPU / 2Gi memory) to pods without resource requests. These defaults are invisible in pod specs — they only appear in `kubectl describe pod` output or `kubectl top`.
2. GKE Warden enforces Autopilot-style minimum floors (50m CPU / 52Mi memory) even on Standard clusters with NAP. Pods requesting below this floor get mutated upward. The `autopilot.gke.io/resource-adjustment` annotation appears on affected Deployments regardless of cluster provisioning type.

## Resolution

Added explicit tiered resource requests to all operator components:

- Controller-class (high CPU/memory): 100m CPU / 128Mi memory
- Webhook-class (moderate): 50m CPU / 64Mi memory
- Batch-class (low, at GKE floor): 50m CPU / 52Mi memory

Tiered profiles prevent NAP inflation and signal workload class to readers. cert-manager cainjector gets extra memory headroom (192Mi) due to known leak history in v1.12.x.

## How to detect

Compare `kubectl top pods` output against declared resource requests. If actual usage is a fraction of requests but requests weren't set by you, NAP defaults are active. Check for `autopilot.gke.io/resource-adjustment` annotations on Deployments.
