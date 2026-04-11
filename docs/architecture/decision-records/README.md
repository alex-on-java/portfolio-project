# Architecture Decision Records

This directory contains Architectural Decision Records (ADRs) for the portfolio-project.

ADRs capture significant architectural decisions: the context, the options considered, the choice made, and its consequences. They follow the [MADR](https://adr.github.io/madr/) (Markdown Any Decision Records) format.

## What belongs here

Decisions that shape the system's structure and are hard to reverse: technology choices, integration patterns, deployment strategies, and structural trade-offs. Each ADR should document a genuine choice between viable alternatives.

## What does not belong here

- Bug fixes or operational incidents — see [Lessons Learned](../../lessons-learned/README.md)
- Configuration details derivable from the code itself
- Decisions that are trivially reversible

## Decision Records

| # | Decision | Status |
|---|----------|--------|
| [ADR-001](ADR-001-gitops-promotion-pipeline-with-kargo-and-argo-rollouts.md) | GitOps promotion pipeline with Kargo and Argo Rollouts | accepted |
| [ADR-002](ADR-002-ephemeral-and-main-cluster-separation.md) | Ephemeral and main cluster separation | accepted |
| [ADR-003](ADR-003-deterministic-commit-pinned-promotions.md) | Deterministic commit-pinned promotions | accepted |
| [ADR-004](ADR-004-helm-for-external-charts-kustomize-for-first-party-manifests.md) | Helm for external charts, Kustomize for first-party manifests | accepted |
| [ADR-005](ADR-005-gateway-api-exposure-with-promotion-time-hostname-injection.md) | Gateway API exposure with promotion-time hostname injection | accepted |
| [ADR-006](ADR-006-contour-over-envoy-gateway-and-nginx-gateway-fabric.md) | Contour over Envoy Gateway and NGINX Gateway Fabric in ephemeral clusters | accepted |
| [ADR-007](ADR-007-contour-for-ephemeral-gcp-managed-gateway-for-main.md) | Contour for ephemeral clusters, GCP managed Gateway for main cluster | accepted |
| [ADR-008](ADR-008-edge-owned-wildcard-tls-and-stage-first-hostnames.md) | Edge-owned wildcard TLS and stage-first hostname contract | accepted |
