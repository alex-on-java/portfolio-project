# LL-0015: GKE Autopilot enforces `ephemeral-storage` request/limit equality

## Summary

On GKE Autopilot, `ephemeral-storage` limits that differ from requests are mutated to match requests. If Git declares a mismatch on ArgoCD-owned fields, this creates persistent OutOfSync drift.

## What happened

A chart preset rendered an init container with a large `ephemeral-storage` limit and much smaller request. Autopilot mutated the live object to equalize values, and ArgoCD continued reporting drift.

## Root cause

Autopilot admission applies platform invariants for `ephemeral-storage` that differ from generic Kubernetes assumptions used by some chart presets.

## Resolution

Set explicit `ephemeral-storage` request and limit with equal values across all relevant containers (including init containers and preset overrides) in source values.

## How to detect

When only `ephemeral-storage` fields drift while CPU/memory remain stable, compare desired vs live values and check for Autopilot mutation behavior in admission/managed field history.
