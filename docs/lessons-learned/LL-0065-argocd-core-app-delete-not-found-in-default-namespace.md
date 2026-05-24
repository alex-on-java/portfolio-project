# LL-0065: `argocd --core app delete` Reports Application Not Found Against a Workload Kube-Context

## Summary

`argocd --core` does not talk to an `argocd-server` over the network. It loads the same server logic in-process and drives it against the kubeconfig that is currently active. The Application namespace is resolved through `clientcmd.ClientConfig.Namespace()` in `cmd/argocd/commands/headless/headless.go`, which honors the `namespace:` field on the current kube-context. If that context points at a workload namespace, the in-process server looks there for `application.argoproj.io/<name>`, finds nothing, and surfaces a `NotFound`-shaped error. The Application is alive in `argocd`; the lookup just never reached it.

## What Happened

During the cluster-release experiment captured in the work log for this branch, an operator ran `argocd --core ... app delete bootstrap --cascade`. Its active kube-context defaulted to a workload namespace. The command failed with the Application apparently missing, even though `kubectl get application/bootstrap -n argocd` listed it. Switching the kube-context's default namespace to `argocd` and rerunning the same command succeeded and triggered the cascade.

An operator familiar with network mode assumes `argocd --core` resolves Applications in the `argocd` namespace by default, on the strength of the word `argocd` in the binary name. The actual resolver has no such bias.

## Root Cause

Two independent mechanisms collide. The `--core` flag swaps the network argocd-server for an in-process equivalent in `cmd/argocd/commands/headless/headless.go`, wired to the same `clientcmd.ClientConfig` the rest of the CLI uses. That config exposes a single `Namespace()` method, and ArgoCD reads it once to scope its Application client. The method's contract is well-known on the Kubernetes side: it returns the current context's `namespace:` field, falling back to `default`. ArgoCD therefore inherits whichever workload namespace the operator happens to be operating in.

The official guidance in [argo-cd.readthedocs.io/en/stable/operator-manual/core/](https://argo-cd.readthedocs.io/en/stable/operator-manual/core/) is one line: *"change current kube context to argocd namespace"*. That instruction is the only signal in the docs that the resolution path runs through the kube-context. Operators familiar with the network mode, where `argocd login` and the server's deployment namespace fix the lookup target, do not expect the kube-context to be load-bearing.

The Application-delete path in `server/application/application.go` resolves the Application by `(namespace, name)` against the Kubernetes API. When the lookup misses, it returns `status.Error(codes.NotFound, …)`. That error surfaces as an Application-not-found message rather than a namespace-mismatch diagnostic; the namespace the lookup actually used is not part of the message. The operator therefore sees "this Application does not exist" and must independently deduce that the lookup was scoped wrong.

## The Override

`argocd app delete` carries `-N`/`--app-namespace string` for exactly this case (CLI reference: [argocd_app_delete](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_delete/)). Passing `-N argocd` pins the Application namespace explicitly and decouples the command from the kube-context's default. The equivalent for read-only listing is `argocd app list -N argocd`. Treat `-N` as required whenever `--core` runs from an environment that may not have switched contexts.

The alternative is to set the kube-context's namespace before invoking the CLI: `kubectl config set-context --current --namespace=argocd`. This is the path the upstream docs recommend. Both work; pinning `-N` per invocation is the more defensive choice for scripted teardowns where the active context is whatever the caller left behind.

## Distinction from LL-0052

[LL-0052](LL-0052-kubectl-cascade-foreground-leaves-argocd-workloads-behind.md) covers why a `kubectl delete` on an ArgoCD Application without the resources-finalizer does not drain managed workloads. This entry is one layer up: even when the operator reaches for `argocd app delete --cascade`, `--core` can fail to find the target Application if the kube-context's namespace is wrong. The two entries describe failure modes at adjacent stages of the same teardown path. They compound: a workflow that recovers from LL-0052 by switching to `argocd --core app delete` lands directly on this one if the context is not pre-set.

## How to Detect

`argocd --core app delete <name>` returning a not-found-shaped error against an Application that `kubectl get application/<name> -n argocd` lists is the canonical signature. Confirm with:

```bash
kubectl config view --minify -o jsonpath='{.contexts[0].context.namespace}'
```

Any value other than `argocd` (including empty, which resolves to `default`) means the in-process server will scope its lookup somewhere other than where the Application lives. The read-side signature is symmetric: `argocd --core app list` returns an empty list silently rather than an error. An empty list against a cluster known to host Applications is the same failure observed from the read side.

## Adoption Rule

Any teardown or incident-response script that uses `argocd --core` against an Application in `argocd` must either set the kube-context namespace to `argocd` first, or pass `-N argocd` on every command. Do not rely on the binary name `argocd` to imply a default namespace; the `--core` resolver has no such default. Prefer `-N` in scripted paths because the active kube-context is environmental state the script does not own.
