# LL-0001: GKE Warden Denies kube-system Writes, Breaking cert-manager

**Summary**: GKE Warden denies writes to `kube-system` (managed namespace). cert-manager cainjector's leader election defaults to `kube-system`, causing an invisible failure where all pods show Running but the webhook is broken.

## What happened

After deploying cert-manager on GKE, all three pods (controller, webhook, cainjector) showed Running/Ready status. However, every cert-manager resource (Certificate, Issuer, ClusterIssuer) failed with x509 validation errors. The webhook's `caBundle` field was empty.

## Root cause

cert-manager cainjector performs leader election in `kube-system` by default. GKE Warden (the admission controller for managed namespaces) blocks writes to `kube-system`. cainjector fails to acquire its leader lease, so it never injects CA bundles into the webhook configuration. The failure is silent — cainjector logs the error but the pod stays Running because leader election retry is not a crash condition.

## Resolution

Set `global.leaderElection.namespace: cert-manager` in the Helm values. This redirects leader election to cert-manager's own namespace, which is not GKE-managed.

## How to detect

Check `kubectl get mutatingwebhookconfigurations cert-manager-webhook -o jsonpath='{.webhooks[0].clientConfig.caBundle}'` — if empty, cainjector is not injecting. Check cainjector logs for `kube-system` lease errors.
