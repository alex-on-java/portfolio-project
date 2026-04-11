# LL-0013: Helm `skipCrds` is all-or-nothing under CRD channel policy constraints

## Summary

`skipCrds` disables all CRD installation from a chart. In environments with CRD channel enforcement, this can avoid one policy violation while introducing another missing-CRD failure mode.

## What happened

The edge controller chart attempted to reconcile in a cluster where Gateway API channel policy rejected certain CRDs. Enabling `skipCrds` removed policy-denied applies, but also blocked chart CRDs that the controller needed.

## Root cause

`skipCrds` has no selective scope. It cannot distinguish between disallowed CRDs and required CRDs in the same chart payload.

## Resolution

Avoid relying on all-or-nothing `skipCrds` as the steady-state fix when chart CRD composition conflicts with platform policy. Prefer an architecture/controller path that does not require this compromise.

## How to detect

If sync alternates between admission-denied CRD errors and missing-kind/controller startup failures after enabling `skipCrds`, treat this as a chart/policy incompatibility rather than an isolated sync glitch.
