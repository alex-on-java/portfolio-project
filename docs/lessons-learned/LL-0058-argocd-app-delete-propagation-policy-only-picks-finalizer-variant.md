# LL-0058: `argocd app delete --propagation-policy` Picks a Finalizer Variant, Not a `kubectl` Propagation Mode

## Summary

`argocd app delete --propagation-policy=foreground|background|orphan` looks like a passthrough to the `metav1.DeleteOptions.PropagationPolicy` field, the same shape `kubectl delete --propagation-policy=...` sends to the apiserver. The flag never reaches that field. Argocd-server's `Application.Delete` handler reads the value and picks one of three finalizer string variants (`resources-finalizer.argocd.argoproj.io`, `.../foreground`, `.../background`). It patches that finalizer onto the Application CR, then issues `Applications().Delete(ctx, name, metav1.DeleteOptions{})` against the apiserver with an empty `DeleteOptions`. Later, the ArgoCD application controller consumes the flag indirectly. `finalizeApplicationDeletion` reads the finalizer back and translates it into the `metav1.DeletePropagation*` it passes on each managed-resource delete. The apiserver call that removes the Application itself never sees the flag.

## What Happened

One teardown experiment used `argocd --core app delete bootstrap --cascade --propagation-policy=background`, expecting the apiserver to garbage-collect the Application object under background propagation. The observed timing did not match: the CLI returned in seconds while the workload tree drained over the next two minutes. A parallel run with `--propagation-policy=foreground` ran end-to-end with similar workload-deletion semantics, but the Application CR persisted under `deletionTimestamp` for the same window. Switching the flag changed neither *who* deleted the workloads nor *when* the apiserver removed the Application. What it changed was the `metav1.DeletePropagation*` the application controller stamped on each per-resource delete during its own cascade walk.

## Root Cause

In `server/application/application.go`, `(s *Server) Delete` (around line 1550) builds the patch from the flag:

```go
policyFinalizer := getPropagationPolicyFinalizer(q.GetPropagationPolicy())
if policyFinalizer == "" {
    return nil, status.Errorf(codes.InvalidArgument,
        "invalid propagation policy: %s", *q.PropagationPolicy)
}
// ... a.SetCascadedDeletion(policyFinalizer); patch metadata.finalizers ...
err = s.appclientset.ArgoprojV1alpha1().Applications(appNs).
    Delete(ctx, appName, metav1.DeleteOptions{})
```

That `Delete` call uses a zero-valued `metav1.DeleteOptions{}`, with no `PropagationPolicy` and no `GracePeriodSeconds`. The three string variants are defined in `pkg/apis/application/v1alpha1/application_defaults.go`:

```
ResourcesFinalizerName               = "resources-finalizer.argocd.argoproj.io"
ForegroundPropagationPolicyFinalizer = "resources-finalizer.argocd.argoproj.io/foreground"
BackgroundPropagationPolicyFinalizer = "resources-finalizer.argocd.argoproj.io/background"
```

Then the application controller consumes the choice in `finalizeApplicationDeletion` (`controller/appcontroller.go`):

```go
propagationPolicy := metav1.DeletePropagationForeground
if app.GetPropagationPolicy() == appv1.BackgroundPropagationPolicyFinalizer {
    propagationPolicy = metav1.DeletePropagationBackground
}
```

`propagationPolicy` then rides on each `kubectl.DeleteResource(...)` call the controller issues against managed live objects. That is the only place the CLI's flag becomes a Kubernetes propagation mode, and it applies to the children, not to the Application object.

So the flag controls two things at once, neither of which is what its name suggests. It picks the finalizer string variant the server patches onto the Application, and through that finalizer it picks the propagation policy the controller uses for the per-child delete loop. The apiserver call against the Application itself is unaffected, and `kubectl get application/<name> -o yaml` will show whichever finalizer variant the flag selected, not the propagation policy itself.

## Why It Looks Like a Passthrough

The CLI flag name reuses Kubernetes vocabulary verbatim. Its accepted values (`foreground`, `background`, `orphan`) are the same three values `kubectl delete --propagation-policy=...` accepts. A natural reading is that argocd-server forwards the value to the apiserver. The actual implementation overloads the term: the same word names a Kubernetes apiserver behavior and an ArgoCD finalizer-selection behavior. The ArgoCD User Guide describes the controller-driven cascade but does not call out that the flag never reaches `metav1.DeleteOptions`. So the misreading is consistent with the public surface and only resolves against the source.

## Distinction from LL-0052

[LL-0052](LL-0052-kubectl-cascade-foreground-leaves-argocd-workloads-behind.md) covers the inverse misreading. The flag `kubectl delete --cascade=foreground` looks like an ArgoCD cascade but is a Kubernetes ownerReference garbage-collection mode that finds nothing to collect on ArgoCD-managed trees. This entry covers the symmetric trap on the ArgoCD CLI side. The flag `argocd app delete --propagation-policy=...` looks like a Kubernetes propagation mode but is an ArgoCD finalizer-variant selector. Its value never reaches the apiserver on the Application delete. Both entries describe a shared-vocabulary collision around the words "cascade" and "propagation policy"; LL-0052 covers the `kubectl` direction, this entry covers the `argocd` CLI direction.

## How to Detect

Symptoms that the flag is being misread:

- An operator expects `--propagation-policy=foreground` to make the apiserver hold the Application CR until dependents are gone, and is surprised when no Application object carries ownerReferences from managed workloads.
- A teardown step measures Application-deletion latency against the flag value and observes no clear pattern, because the value is consumed by the controller's per-child deletes, not the Application delete itself.
- `kubectl get application/<name> -n argocd -o jsonpath='{.metadata.finalizers}'` after the CLI invocation shows one of the three finalizer string variants instead of the propagation policy.

Confirm by inspecting the finalizer the server patched in:

```bash
kubectl get application/<name> -n argocd -o jsonpath='{.metadata.finalizers}'
# expect one of:
#   ["resources-finalizer.argocd.argoproj.io"]
#   ["resources-finalizer.argocd.argoproj.io/foreground"]
#   ["resources-finalizer.argocd.argoproj.io/background"]
```

The variant is the durable record of the flag value; the apiserver delete call carries no trace of it.

## Adoption Rule

Treat `argocd app delete --propagation-policy=...` as a controller-side knob, not an apiserver-side one. The default value `foreground` (used when `--cascade` is passed without an explicit policy) makes the controller delete each managed resource with `metav1.DeletePropagationForeground` and wait per-resource for dependents to clear. The alternative value `background` makes the controller issue background deletes against managed resources and return sooner; dependents then clean up asynchronously.

Do not pass the flag expecting it to change how the apiserver garbage-collects the Application CR itself. That path is governed entirely by the finalizers on the Application and the controller that removes them. Apiserver-side propagation of the Application object generally does not matter, since managed workloads carry no ownerReferences back to the Application. If it ever does matter, use `kubectl delete application/<name> --cascade=...` instead, with the finalizer-presence prerequisite from [LL-0052](LL-0052-kubectl-cascade-foreground-leaves-argocd-workloads-behind.md).
