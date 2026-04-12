# LL-0012: Helm hook jobs can stall ArgoCD reconciliation without explicit delete policy

## Summary

A Helm hook Job can keep ArgoCD operations stuck when stale or immutable hook resources remain attached to the active sync operation. Explicit hook delete policy is required to keep retries convergent.

## What happened

A pre-sync cert generation hook remained pending with outdated pod-template constraints. Even after values changes in Git, the running operation stayed attached to stale hook resources, and reconciliation did not converge.

## Root cause

Hook resources are separate lifecycle objects. Without explicit deletion behavior, retries may reuse or remain blocked by older hook instances whose pod templates are immutable and no longer represent desired state.

## Resolution

Add explicit Helm hook delete policy (`before-hook-creation,hook-succeeded,hook-failed`) so each reconciliation attempt can recreate a clean hook lifecycle and avoid stale-operation pinning.

## How to detect

If an ArgoCD app is repeatedly in a running/pre-sync state with a pending hook Job, inspect hook annotations and whether hook objects are being garbage-collected between retries.
