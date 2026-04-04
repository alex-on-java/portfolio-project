# LL-0007: Kustomize Overlays Cannot Reference YAML Above Directory

**Summary**: Kustomize security restriction prevents overlay `kustomization.yaml` files from referencing plain YAML files outside their directory tree. Directory references with their own `kustomization.yaml` are treated as separate roots and are allowed.

## What happened

Kargo project-level resources (`project.yaml`, `project-config.yaml`, `cluster-promotion-task.yaml`) needed to be shared across overlays (ephemeral, main). Referencing them as `../../project/project.yaml` from an overlay failed with a Kustomize security error.

## Root cause

Kustomize restricts resource references to files within or below the kustomization root directory. This is a security measure to prevent overlays from pulling in arbitrary files from the filesystem. However, *directory* references that contain their own `kustomization.yaml` are exempt — Kustomize treats them as independent kustomization roots with their own security boundary.

## Resolution

Wrapped the shared resources in a `project/` directory with its own `kustomization.yaml` that lists the three resources. Overlays reference `../../project` (a directory) instead of individual YAML files.

## How to detect

`kustomize build` fails with a security/path restriction error mentioning files outside the root.
