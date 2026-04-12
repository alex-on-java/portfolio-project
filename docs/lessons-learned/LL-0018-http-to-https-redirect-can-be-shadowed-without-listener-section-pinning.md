# LL-0018: HTTP→HTTPS redirect can be shadowed unless workload routes are pinned to the HTTPS listener

## Summary

Adding an HTTP redirect route is not sufficient by itself when workload `HTTPRoute` objects still attach to both listeners. Without explicit listener pinning, workload host routes can shadow the redirect route on the HTTP listener.

## What happened

A redirect route was added to force HTTP traffic to HTTPS. Despite that, requests still reached workload routes over HTTP for known hostnames. The redirect appeared configured but ineffective.

## Root cause

Workload `HTTPRoute` resources did not specify `sectionName`, so they attached broadly. As a result, host-specific workload routes matched HTTP traffic and took precedence over the generic redirect intent.

## Resolution

Use both controls together:

1. Add an HTTP redirect route on the HTTP listener.
2. Pin workload routes to the HTTPS listener using `parentRefs.sectionName: https`.

This preserves normal HTTPS routing behavior while allowing the HTTP listener to be dedicated to redirects.

## How to detect

If HTTP requests for known hostnames return workload responses instead of `301` redirects:

1. Inspect workload `HTTPRoute` attachments and check for missing `sectionName`.
2. Confirm whether those routes are bound to both listeners.
3. Verify the redirect route is attached to the HTTP listener and no host-specific workload route is shadowing it there.
