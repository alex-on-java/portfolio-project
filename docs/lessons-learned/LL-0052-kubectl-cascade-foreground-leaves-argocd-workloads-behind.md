# LL-0052: `kubectl delete --cascade=foreground` Does Not Drain ArgoCD-Managed Workloads

## Summary

`kubectl --cascade=foreground` and ArgoCD's cascaded deletion share the word "cascade" and nothing else. The `kubectl` flag is a Kubernetes garbage-collection mode that walks `metadata.ownerReferences` on the apiserver. ArgoCD-managed workloads carry no ownerReference back to their Application; they are tracked by the `app.kubernetes.io/instance` label. ArgoCD's cascade runs only when the `resources-finalizer.argocd.argoproj.io` finalizer is present on the Application CR. That finalizer is what enrols the application controller to walk the live tree before allowing the Application to vanish. With the finalizer absent, as it is when an ApplicationSet sets `template.metadata.finalizers: []`, the kubectl flag drives no workload deletion. The Application CR disappears; every managed Deployment, Service, and namespace stays behind.

## What Happened

A teardown invoked `kubectl delete application/bootstrap --cascade=foreground` and then waited on `kubectl wait --for=delete` as the cascade-completion signal. The bootstrap Application was generated with an empty finalizer list (the ephemeral-overlay suppression documented in [LL-0005](LL-0005-application-deletion-hangs-despite-preserve-resources.md)). Its CR was removed promptly by the apiserver, the wait returned success, and the teardown step reported green. Downstream Terraform `Network: terraform destroy` then failed against `k8s-<cluster-uid>-node-http-hc` and a tree of LoadBalancer Services, namespaces, and child Applications that the cascade was assumed to have drained. Restoring the finalizer unconditionally in `infra/bootstrap/main.tf` made the next manual `kubectl delete --cascade=foreground` drain the same tree in roughly 2.5 minutes.

## Root Cause

The two cascades evaluate against different inputs. A kubectl call sets the `metav1.DeleteOptions.PropagationPolicy` on the apiserver delete; the apiserver then garbage-collects any object whose `metadata.ownerReferences` names the deleted Application. Resources reconciled by ArgoCD carry no such ownerReference. See [the Kubernetes garbage-collection documentation](https://kubernetes.io/docs/concepts/architecture/garbage-collection/) for the propagation-policy contract and [the ArgoCD App Deletion guide](https://argo-cd.readthedocs.io/en/stable/user-guide/app_deletion/) for the finalizer-driven alternative. The apiserver finds nothing to collect and removes the CR immediately.

ArgoCD's cascade runs through a different actor. Its application controller subscribes to Applications carrying `resources-finalizer.argocd.argoproj.io` (or one of its propagation-policy variants) and walks the managed live tree in `finalizeApplicationDeletion` (source: `controller/appcontroller.go`). Once the live set is empty, the controller removes its own finalizer. Only then does the apiserver remove the Application. `argocd app delete --cascade` guarantees this path by patching the finalizer in before the delete; `kubectl delete` does not.

`kubectl wait --for=delete` compounds the failure mode silently. On an Application with no finalizer it returns the moment the apiserver removes the CR, within seconds rather than minutes. That reads as a successful cascade in workflow logs and tricks the operator into believing the workload tree drained.

## The Two Levers

For `kubectl delete` to drive an ArgoCD cascade, the finalizer must already be on the Application before the delete call lands. Two independent code paths can put it there, and either is enough.

The **declarative lever** includes `resources-finalizer.argocd.argoproj.io` in `metadata.finalizers` in the source manifest. When an ApplicationSet generates the Application, that manifest is the `template:` block. Setting `template.metadata.finalizers: []` (the ephemeral-cluster suppression) defeats this lever and is the configuration that produced the symptom above.

The **CLI lever** invokes `argocd app delete --cascade`, which patches the finalizer onto the CR before issuing the delete (source: `server/application/application.go`, `(s *Server) Delete`). It works on Applications that carry no finalizer in Git, at the cost of an `argocd` CLI dependency in the teardown environment and a separate ArgoCD RBAC surface.

This teardown chose the declarative lever: drop the ephemeral conditional on the bootstrap Application finalizer in Terraform, then keep using `kubectl delete --cascade=foreground` from the workflow. The flag is still useful with the finalizer present, because the kubectl-side wait gains meaning when the apiserver holds the CR while the controller drains.

## Distinction from LL-0005

[LL-0005](LL-0005-application-deletion-hangs-despite-preserve-resources.md) covers the inverse symptom: the finalizer was present, and Application deletion hung because the workload-drain target cluster was being torn down. Its fix was to keep both finalizer sources suppressed on ephemeral clusters. This entry is the consequence of that suppression in a new context: a teardown path that depends on the cascade now finds none, and `kubectl --cascade=foreground` cannot substitute. The two entries describe opposite ends of the same lever.

## How to Detect

A clean-looking `kubectl delete application/<name>` followed by `kubectl wait --for=delete` returning in seconds, against a non-trivial managed tree, is the canonical signature. Confirm with:

```bash
kubectl get application/<name> -n argocd -o jsonpath='{.metadata.finalizers}'
```

Empty output (`[]` or no key at all) means the kubectl call will never drive an ArgoCD cascade, regardless of the `--cascade` mode passed. After the delete, the residue is directly observable. Managed Deployments and Services still appear under `kubectl get -A -l app.kubernetes.io/instance=<name>`; namespaces stay `Active`; downstream Terraform destroys fail on CCM-leaked firewalls and in-use VPC resources.

## Adoption Rule

A teardown path that uses `kubectl delete` against an ArgoCD Application must satisfy one of the two levers above before the delete call. Verify the finalizer is present on the live resource (declarative lever), or invoke `argocd app delete --cascade` instead (CLI lever). Do not rely on `--cascade=foreground` or `--cascade=background` to substitute; the flag controls Kubernetes garbage collection of ownerReference-linked dependents, which is not how ArgoCD tracks managed workloads.
