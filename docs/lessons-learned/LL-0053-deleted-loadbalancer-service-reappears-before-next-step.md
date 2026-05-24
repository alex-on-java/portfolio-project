# LL-0053: Deleted LoadBalancer Service Reappears Before the Next Teardown Step Reads It

## Summary

A pre-teardown step bulk-deleted LoadBalancer Services so that the cloud load balancer would disappear before any other dismantling began. The deletion succeeded at the API server, then `argocd-application-controller` re-created the same Service within roughly 166 ms because the Service belongs to an `Application` with `automated.selfHeal: true`. Downstream teardown steps therefore observed the re-created Service. In GCP the cloud-controller-manager provisioned a second generation of per-Service firewalls behind the new load balancer. When the cluster was eventually deleted, the cluster-scoped health-check firewall keyed by the GKE cluster UID was left behind. The originally intended "delete once and it stays gone" assumption does not hold while ArgoCD is still running.

## What Happened

A destroy path in `.github/workflows/cluster-lifecycle.yml` ran `kubectl delete svc --all-namespaces --field-selector spec.type=LoadBalancer` before tearing down ArgoCD. Intent was to make the GCP load balancer disappear early, so later steps would not race against in-flight cloud reconciliation. Audit logs from run #139 record the actual sequence:

1. `kubectl delete` removed `projectcontour/contour-envoy` at 20:14:54.466.
2. At 20:14:54.632, just 166 ms later, `system:serviceaccount:argocd:argocd-application-controller` re-created the same Service. Its `Application` (produced by the contour `ApplicationSet` at `gitops/platform/argocd/bootstrap/base/contour-helm-appset.yaml`) carries `syncPolicy.automated.selfHeal: true`. The controller therefore treated the deletion as drift from Git and reconciled the Service back into existence.
3. Between 20:15:29 and 20:16:50 the GCP cloud-controller-manager provisioned a fresh generation of per-Service firewalls for the recreated load balancer.
4. CCM keys the cluster-scoped `k8s-<cluster-uid>-node-http-hc` firewall by GKE cluster UID and never deletes it on Service rotation. It survived into `gcloud container clusters delete` and was orphaned in the project. The subsequent `terraform destroy` of the VPC failed with `is already being used by 'firewalls/k8s-<cluster-uid>-node-http-hc'`.

That cleanup step, intended to drain the load balancer, instead caused a second load balancer to be provisioned and left a cluster-scoped firewall behind.

## Root Cause

`kubectl delete svc` is a terminal call against the kube-apiserver: when it returns, the Service is gone from etcd. The same call is not terminal against an ArgoCD `Application` whose `syncPolicy.automated.selfHeal: true` enrolls the application controller as a recreator. Whenever a managed resource disappears from live state while desired state in Git still includes it, the controller observes the deletion as drift. It then issues a `CREATE` on the next reconciliation pass. In this cluster the gap between the apiserver `DELETE` and the controller `CREATE` was 166 ms, too short for any downstream teardown step to observe a `LoadBalancer`-free state.

A deeper problem is the implicit assumption that an API-server success implies a stable absence. On an ArgoCD-managed cluster the implication holds only after the controller is gone or its parent `Application` no longer carries `selfHeal`. While `argocd-application-controller` is running and the parent stays healthy, every `kubectl delete` on a managed Service is reconciled away within one tick.

This pattern generalises beyond LoadBalancer Services. Any managed resource is reconciled back the same way, whether `Deployment`, `ConfigMap`, or `Ingress`. `LL-0035` records the same shape for `ProjectConfig` and `RoleBinding` patches during a Kargo migration. SelfHeal wins against any cluster-side mutation that races a controller reconciliation.

## Resolution

The destroy path was redesigned around an ArgoCD cascade rather than a pre-emptive Service delete:

1. `kubectl delete application/bootstrap -n argocd --cascade=foreground` drives the controller to drain its entire managed tree. Cascade deletion subsumes LoadBalancer cleanup. Each `Application` deletes its own resources before its finalizer clears. Controllers themselves are torn down as part of the cascade, so no actor remains to re-create anything.
2. A separate `kubectl wait --for=delete application/bootstrap -n argocd --timeout=30m` blocks until the cascade actually completes. Passing `--wait=false` on the delete and following with this explicit wait separates the API-server return value from the drain predicate.
3. The pre-emptive `kubectl delete svc` step and the redundant `scripts/cleanup-argocd.sh` invocation were removed; the script itself was deleted from the repository.

Phase-3 live verification on a real PR cluster recorded zero self-heal events during cascade. At t+121 s `lbs=0` confirmed that `contour-envoy` drained with its parent `Application` rather than being recreated.

## How to Detect

Symptoms that a teardown step is racing ArgoCD self-heal:

- A `kubectl delete` of a managed resource returns success, but a `kubectl get` issued shortly after shows the resource present again with a new `creationTimestamp` and a different UID.
- Audit logs attribute the deletion to the workflow service account and the recreation to `system:serviceaccount:argocd:argocd-application-controller` (or the equivalent for the local install).
- Downstream cloud-provider side-effects (firewalls, target pools, forwarding rules, DNS records) appear in *two generations* per run, with the second generation created after the cleanup step is supposed to have finished.

When designing a teardown of an ArgoCD-managed cluster, prefer to issue the delete through the ArgoCD cascade. Both `argocd app delete --cascade` and `kubectl delete application/<app> --cascade=foreground` work against an `Application` that carries `resources-finalizer.argocd.argoproj.io`. Cascade is the only path that removes the controller and its managed resources in the right order. Any direct cluster-side delete of a managed resource while the controller is alive is undone before the next step can observe the absence.
