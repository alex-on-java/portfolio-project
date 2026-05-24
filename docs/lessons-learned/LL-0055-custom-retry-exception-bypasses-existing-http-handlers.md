# LL-0055: Custom Retry-Wrapper Exception Bypasses Existing `requests.HTTPError` Handlers

## Summary

A `@tenacity.retry(..., reraise=True)` decorator wraps a GitHub API helper and raises a custom `TransientHTTPError(Exception)` on persistent 5xx. The exhausted retry surfaces *that* class at the call site, not `requests.HTTPError`. Existing handlers shaped as `except requests.HTTPError` do not match it. Python `except` clauses dispatch on the class hierarchy of the exception object, not on the causal chain that produced it. The retry budget exhausts, the cluster sits in `DESTROYING`, and the unhandled traceback escapes the operator.

## What Happened

`pool_ctl/github.py` introduced retry-with-backoff around the GitHub workflow-status poll. `_fetch_run_status` was wrapped with

```python
@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, TransientHTTPError)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=(stop_after_attempt(5) | stop_after_delay(90)),
    reraise=True,
)
```

A response with `status_code >= 500` raised `TransientHTTPError(Exception)`, defined locally as a bare `Exception` subclass holding the status code. The `release` command in `pool_ctl/main.py` (around lines 680-706, before the fix) caught `(requests.ConnectionError, requests.Timeout, TimeoutError)` and then `requests.HTTPError`. Neither clause named `TransientHTTPError`. On persistent 5xx, `reraise=True` propagated `TransientHTTPError` to `release`; no handler matched. Operator process died with an unhandled exception and the cluster row stayed in `DESTROYING`. Exactly the failure mode the retry layer was meant to eliminate.

A pre-merge Codex review flagged this as a blocker. The verification sub-agent then reproduced the gap against three concrete sites. In `github.py:21`, `_TransientHTTPError` was a bare `Exception` subclass. At `main.py:679-706`, the except chain in `release()` covered connection errors and `requests.HTTPError` only. The same hole existed in `final_run_status_check` at `github.py:143`.

## Root Cause

Python exception handling dispatches by the runtime class hierarchy of the raised object. An `except` clause matches the raised class and its subclasses, and nothing else. `TransientHTTPError(Exception)` is not a subclass of `requests.HTTPError`. It inherits from bare `Exception`. The cause that produced it, a 5xx HTTP response, is irrelevant to the match. `__cause__` and `__context__` do not participate in `except` resolution.

Tenacity's `reraise=True` is what makes this visible. By default tenacity wraps a retry-exhausted failure in `RetryError`. With `reraise=True` set, the wrapper is stripped and the last underlying exception surfaces unchanged. That is the intentional design described in the tenacity documentation. The handler at the call site then sees `TransientHTTPError` itself, not `RetryError`, and not `requests.HTTPError`. A reviewer reading the retry list can absorb the misconception that its three classes are interchangeable from the caller's point of view. They are not. That list names interchangeable inputs to tenacity's retry predicate, but distinct outputs at the call site.

One more factor amplified the surprise. The class was named with a leading `_` (`_TransientHTTPError`) and lived in the same module as the wrapped helper. A reader scanning `release` for "what could escape this call" would not search for a private name from another module. Private name and cross-module escape contradicted each other; the type system did not flag it, since a bare `Exception` is assignable to anything.

## Resolution

Two complementary edits close the gap without papering over it.

First, the custom exception is named in every `except` chain that handles HTTP-layer failures from the wrapped function. In `pool_ctl/main.py`:

```python
try:
    conclusion = destroy_wait(token, infra_repo, run_id)
except (
    requests.ConnectionError,
    requests.Timeout,
    TimeoutError,
    TransientHTTPError,
) as exc:
    conclusion = final_run_status_check(token, infra_repo, run_id, deadline_seconds=120)
    if conclusion is None:
        _update_cluster_in_state(bucket, target.name, ClusterState.DESTROY_FAILED)
        sys.exit(1)
except requests.HTTPError as exc:
    ...
```

`final_run_status_check` in `pool_ctl/github.py` similarly extends its `except` tuple to include `TransientHTTPError`. The post-fix tuple is `(requests.ConnectionError, requests.Timeout, requests.HTTPError, TransientHTTPError)`.

Second, the class is renamed from `_TransientHTTPError` to `TransientHTTPError` and treated as a public part of the module's API. The leading `_` was a fiction. Tenacity's `reraise=True` already crossed module boundaries with that class. Operator code at the call site genuinely needed to know about it: *exhausted-transient* carries a different semantic from *hard 4xx*. Dropping the leading `_` aligns the name with the actual reachability of the class.

## Adoption Rule

A retry decorator that raises any non-stdlib exception class, whether `tenacity.RetryError`, a project-local `TransientHTTPError`, or any other custom signal, defines a part of the wrapped function's public API. Every call site that previously caught the underlying library's exceptions must extend its `except` chain to include the new class explicitly. The retry predicate's `retry_if_exception_type(...)` tuple lists what tenacity *consumes*; the class that the decorator *emits* on exhaustion is a separate concern and is not visible from that tuple.

Two structural alternatives exist where they fit:

- Subclass the closest existing library exception (`class TransientHTTPError(requests.HTTPError)`), so existing handlers continue to match. Appropriate when the new class genuinely is-a refinement of the library exception. Inappropriate when the new class carries different semantics that the caller must distinguish; here, "GitHub is throttling or 5xx-ing, retry exhausted" is meaningfully different from "GitHub returned a hard 4xx".
- Catch the custom class inside the retry wrapper and translate it back to a library exception before re-raising. This shifts the surprise from the call site to the wrapper. The move fits only when the wrapper is a thin adapter and the library exception is the documented API.

Whichever path is chosen, the choice must be visible at the call site. A private name on a class that escapes the module is the wrong signal.

## How to Detect

Symptoms of a retry wrapper whose escape class is not in any caller's handler set:

- An operator dies with an unhandled traceback whose top frame is the caller of a `@retry`-decorated function, and whose innermost frame names a project-local exception class. The retry list in the decorator includes that same class.
- The call site has a chain of `except` clauses for the underlying library's exceptions (`requests.HTTPError`, `requests.ConnectionError`, and similar) but does not name the project-local class.
- The decorator's `reraise=True` is set, so the surfacing class is the underlying exception rather than `tenacity.RetryError`. Without `reraise=True` the same gap exists, but manifests as an unhandled `RetryError` instead.
- The custom class is defined as a bare `Exception` subclass, so static type checkers do not flag the missing handler.

One targeted check at review time: grep the decorated function's module for `raise <CustomClass>`, then grep every caller for that class name in an `except`. A retry decorator whose raise-set is not a subset of every caller's catch-set is the failure mode this entry records.
