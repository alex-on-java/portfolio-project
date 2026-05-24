# LL-0062: Tenacity `stop_after_attempt` Does Not Bound the Wall-Clock Cost of One Invocation

## Summary

`stop_after_attempt(N)` bounds the count of attempts a tenacity-wrapped call makes, not the wall-clock it consumes. With a per-request timeout of T, one invocation can spend up to N times T inside HTTP calls, plus the cumulative `wait_exponential` backoff between attempts, before re-raising. Under an outer polling loop that owns its own deadline, the inner attempt budget is invisible to the outer ceiling. The fix is to combine `stop_after_attempt(N)` with `stop_after_delay(seconds)` via the `|` operator, so the first condition to trip ends the retry sequence.

## What Happened

In `pool_ctl/github.py`, `poll_workflow` runs a 45-minute outer loop that calls `_fetch_run_status` every 30 seconds against the GitHub Actions API. The release path uses this to wait for the infra `cluster-lifecycle.yml` workflow to drain a cluster. An earlier draft of the retry decorator stopped only on attempt count:

```python
stop=stop_after_attempt(5)
```

Each underlying GET runs with `_POLL_TIMEOUT = 15` and `wait_exponential(min=1, max=30)` between attempts. Worst-case cost of one `_fetch_run_status` call is then roughly 5 times 15 seconds of HTTP-timeout, plus four backoff waits capped at 30 seconds each. That is on the order of three minutes per invocation. The outer 45-minute ceiling does not detect this: the deadline is checked at loop entry, not during a wrapped call.

A single sustained 5xx or connection-error episode can therefore consume a non-trivial slice of the operator-facing 45-minute budget while the loop appears stuck on one iteration. Worse, an iteration that starts just before the deadline runs past it by up to one inner retry window.

## Root Cause

Tenacity `stop` conditions are independent predicates evaluated after each attempt. One predicate, `stop_after_attempt(N)`, returns true once N attempts have occurred. Its sibling `stop_after_delay(seconds)` returns true once cumulative wall-clock since the first attempt exceeds the limit. Neither implies the other. Under a combined stop, a retry sequence may exhaust its attempt budget after 75 seconds, or give up after 90 seconds on the third attempt; both outcomes are valid.

The implicit assumption "N attempts is a wall-clock proxy" holds only when per-request timeout is small and backoff is absent. As soon as either changes, attempt count and wall-clock decouple. An outer loop that owns a wall-clock budget must combine both stops to keep the inner cost predictable.

## Resolution

The current decorator on `_fetch_run_status` declares both stops with a logical OR, so the first to trip wins:

```python
@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout, TransientHTTPError)),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=(stop_after_attempt(5) | stop_after_delay(90)),
    reraise=True,
)
def _fetch_run_status(...): ...
```

With this combined stop, one invocation cannot exceed 90 seconds of wall-clock regardless of backoff, and cannot make more than five HTTP attempts regardless of how fast each one fails. The 45-minute outer ceiling now bounds the number of poll cycles, not an unknown product of cycles and retries.

`_POLL_TIMEOUT` is 15 seconds for the polling-class GET, so a failure feeds the retry loop sooner. The constant `_TIMEOUT` stays at 30 seconds for write-side calls like `trigger_workflow` and `create_deployment`, which are not on the retry path.

## How to Detect

Symptoms of an inner retry budget unbounded in wall-clock:

- An outer polling loop with a wall-clock deadline appears to skip iterations or report `TimeoutError` earlier than the configured ceiling.
- A single iteration of the outer loop takes meaningfully longer than the configured per-iteration sleep plus the per-request timeout.
- The retry decorator declares only `stop_after_attempt(...)` and the wrapped function performs a network call whose timeout is non-trivial relative to the outer budget.

When auditing a tenacity decorator inside a polling loop, read the `stop=` argument: if it names only an attempt count, the wall-clock cost is not bounded. Combine with `stop_after_delay` whenever the wrapped function performs I/O on a path that an outer caller deadlines.

## Adoption Rule

Any tenacity-decorated function on a polling path declares a combined `stop=(stop_after_attempt(N) | stop_after_delay(seconds))`. Pick the delay so one worst-case invocation fits comfortably inside one outer poll cycle; that leaves the outer deadline to bound the number of cycles rather than the per-cycle cost. Keep the attempt count as a secondary guard against pathologically fast failures that would otherwise burn the entire delay budget on retries.
