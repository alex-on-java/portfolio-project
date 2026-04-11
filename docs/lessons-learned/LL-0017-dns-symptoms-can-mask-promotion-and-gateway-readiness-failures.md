# LL-0017: DNS symptoms can mask promotion blockage and Gateway/dataplane readiness failures

## Summary

`NXDOMAIN` (or missing upper-stage records) can look like a DNS controller failure even when DNS is working correctly. In staged GitOps promotion flows, the real root cause may be blocked promotion and missing route materialization. Separately, correct DNS alone does not prove Gateway listener validity or dataplane readiness.

## What happened

Upper-stage hostnames (for example `stg`/`prd`) appeared unresolved, which initially suggested DNS breakage. Investigation showed promotion was blocked upstream, so the corresponding `HTTPRoute` objects for upper stages were never materialized. In a related path, DNS records and load balancer addressing were correct, but traffic still failed because Gateway listener configuration/readiness was invalid.

## Root cause

Two independent misconceptions:

1. Missing upper-stage DNS records were interpreted as DNS failure, while the actual issue was promotion pipeline blockage preventing upper-stage route creation.
2. DNS correctness was treated as end-to-end readiness, even though Gateway listener validity and dataplane health are separate convergence domains.

## Resolution

Use layered diagnosis in order:

1. Verify promotion progression and stage freight availability.
2. Verify that stage-specific `HTTPRoute` resources are materialized.
3. Verify DNS record creation from those routes.
4. Independently verify Gateway listener validity/conditions.
5. Independently verify dataplane readiness and request path behavior.

Treat DNS as one checkpoint in the chain, not as proof of full ingress correctness.

## How to detect

When upper-stage hostnames return `NXDOMAIN`:

1. Check whether upper-stage promotions actually completed.
2. Check whether upper-stage routes exist in-cluster.
3. If routes do exist and DNS is present, continue with Gateway condition and dataplane health checks before concluding ingress is healthy.
