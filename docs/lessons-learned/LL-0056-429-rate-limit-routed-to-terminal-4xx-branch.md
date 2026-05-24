# LL-0056: `status_code >= 500` Routes HTTP 429 to the Terminal 4xx Branch

## Summary

An HTTP client that partitions retryable failures from terminal failures by `status_code >= 500` quietly misclassifies HTTP 429. The threshold encodes a folk rule: 5xx is transient, 4xx is permanent. But 429 Too Many Requests sits in the 4xx range, and it is the canonical transient response on any sustained polling path. GitHub uses 429 (and sometimes 403) for both primary and secondary rate limits, with documented retry guidance of exponential backoff honouring `Retry-After`. Under the 5xx-threshold predicate, normal rate limiting surfaces as a terminal `requests.HTTPError`, and the 4xx branch exits as if the request were misconfigured.

## What Happened

`pool_ctl/github.py:_fetch_run_status` wrapped the GitHub Actions run-status GET in tenacity and classified the response with:

```python
if response.status_code >= 500:
    raise _TransientHTTPError(response.status_code)
if 400 <= response.status_code < 500:
    response.raise_for_status()
```

The destroy poll in `release()` calls this helper every 30 seconds for up to 45 minutes against `api.github.com/repos/.../actions/runs/<id>`. A 5xx response routes through tenacity and retries. Inside the same window, a 4xx response raises `requests.HTTPError`, and the outer except chain treats that as a fatal config error and exits non-zero. GitHub's secondary rate limiter returns 429, which lands in the 4xx branch and never reaches the retry budget. On the cluster-pool release path, that gap stranded a cluster in `DESTROYING` on the first throttle. An operator inspecting state had no signal distinguishing "I crashed on throttling" from "I crashed on a real 404."

The predicate was changed to route both 5xx and 429 through `TransientHTTPError`:

```python
if response.status_code == 429 or response.status_code >= 500:
    raise TransientHTTPError(response.status_code)
if 400 <= response.status_code < 500:
    response.raise_for_status()
```

## Root Cause

HTTP status partitioning by "5xx versus 4xx" is a heuristic, not a contract. RFC 6585 introduced 429 explicitly to signal "you sent too many requests in a given time window," with documented client behaviour of wait-and-retry, optionally honouring `Retry-After`. A class-boundary predicate is orthogonal to retryability. Three 4xx codes are transient in practice (408 Request Timeout, 425 Too Early, 429 Too Many Requests). Several 5xx codes are terminal in practice, such as 501 Not Implemented. A `>= 500` predicate compresses a multi-dimensional decision into one inequality, and the dimension it loses is exactly the one rate-limited polling cares about.

GitHub's rate-limit documentation is unambiguous on the behaviour. Its REST API rate-limits page states that exceeding a secondary rate limit returns "a 403 or 429 response," with `Retry-After` carrying the minimum wait, and recommends exponential backoff between retries. The polling profile here matches what GitHub's per-installation and concurrent-request limits target. One GET every 30 seconds, plus other call sites in the same pool process sharing one installation token, is enough load. A single agent operating against a sized-up pool can plausibly hit 429 inside an hour.

The narrower mechanism is that "5xx is server-side, 4xx is client-side" conflates blame with retryability. Rate limiting is server-side throttling expressed through a 4xx response: the server is telling the client what the client should do (slow down), not reporting its own failure. A retry classifier built on the class boundary inverts that intent.

## How to Detect

Three signatures together identify this misclassification:

- The retry-decision predicate is shaped `status_code >= 500` or `status_code // 100 == 5`, with no explicit handling of 429.
- The client polls a third-party API (GitHub, GitLab, container registries, cloud-control planes) on a tight loop or with concurrent workers sharing one token.
- Operator logs show `requests.HTTPError: 429 Client Error` on a path that the change-author believed was retry-protected.

A grep for the predicate alone is sufficient as a code-review check; the runtime symptom requires sustained call volume against a rate-limited backend.

## Adoption Rule

A retry classifier that fronts a rate-limited API must enumerate the transient codes, not subset them by class boundary. For GitHub-style backends, the minimum set is `{408, 425, 429}` together with `5xx`. Some backends return 403 with a rate-limit error body, GitHub primary rate limit among them. Since 403 is also the canonical "permission denied" response, status code alone is insufficient and the classifier must inspect the body. Where `Retry-After` is present, the retry schedule should honour it instead of the local exponential backoff floor.

The same shape applies wherever a predicate compresses a structured taxonomy into one inequality. An inequality is only safe when every member of the included class shares the property the caller depends on, and every member of the excluded class lacks it. For HTTP status codes, neither holds.

## Generalization

A status-class partition is an attractive abstraction because it reads as a tidy invariant: 5xx for them, 4xx for us. But the class boundary was designed for blame attribution between client and server, not for retry classification by the client. Retry decisions need a different cut: codes that mean "try again later," codes that mean "fix your request," codes that mean "stop entirely." Those three sets intersect both classes. A classifier that conflates blame with retryability happens to work on aligned codes and fails on the ones that disagree; 429 is the most common disagreement.
