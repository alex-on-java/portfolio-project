# LL-0063: Successful Destroy Marked `DESTROY_FAILED` After the Final Poll Errored Transiently

## Summary

`pool-ctl release` watches the infra `cluster-lifecycle.yml` workflow run by polling the GitHub Actions API every 30 seconds for up to 45 minutes. On budget exhaustion or retry-chain exhaustion, the operator cannot tell which of two realities produced the exit. Either the workflow run is still executing, or it completed during the in-flight call that just failed. Transitioning straight to `DESTROY_FAILED` on budget exhaustion conflates these realities and can discard a real `success` conclusion. Closing this race requires one final idempotent status read, with its own short budget, before the state transition.

## What Happened

Inside `release`, the destroy path in `pool_ctl/main.py` calls `destroy_wait` (a thin wrapper over `poll_workflow`). An early implementation handled `requests.ConnectionError`, `requests.Timeout`, and `TimeoutError` by jumping straight to `_update_cluster_in_state(..., ClusterState.DESTROY_FAILED)` and exiting non-zero. The transient-error branch and the budget-exhausted branch shared the same handler, so they shared the same blind spot: neither path knew whether the workflow run had already completed.

`portfolio-project-infra/docs/investigations/cluster-release-failures.md` records the operational pattern. Five of twelve destroy runs ended with pool-state entries stuck in `DESTROYING` and stage branches left behind, each one requiring manual recovery. That recurrence rate (around 42 percent) was high enough to make the race window observable on real production traffic, not theoretical.

A new helper, `final_run_status_check` in `pool_ctl/github.py`, performs one best-effort GET against the run ID, retried under tenacity, capped at 120 seconds. From inside the transient and timeout except clause, `release` calls this helper and marks `DESTROY_FAILED` only when the secondary check returns `None`. On a `success` return, the cluster is removed normally. The last polling error was real, but the underlying operation had already finished.

## Root Cause

A polling loop with a wall-clock ceiling has three terminal events that callers often handle uniformly: a completed-status response, an exception, and budget expiry between polls.

These events differ in what they tell the caller about the underlying operation. A completed-status response is dispositive: the operation finished and the conclusion is known. An exception or a budget expiry is indeterminate. The last in-flight call may have raced a completion that landed on the backend just as the request timed out, or just as the deadline passed.

When a handler maps an exception or a budget expiry directly to a terminal failure transition, it is asserting that the operation did not complete. That assertion cannot stand without a follow-up read. The same logical gap appears for any backend job whose completion is observable only by polling: a workflow run, a Terraform apply, a cluster delete.

One follow-up read closes the gap because it is idempotent. A successful GET against the same run ID either confirms completion (with a real conclusion) or surfaces a still-running status that justifies the original failure transition. The tight budget on the secondary check (120 seconds in `pool-ctl`) prevents the recovery path from itself becoming an unbounded retry loop.

## Resolution

The release path now branches on the outcome of `final_run_status_check`:

```python
try:
    conclusion = destroy_wait(token, infra_repo, run_id)
except (requests.ConnectionError, requests.Timeout, TimeoutError, TransientHTTPError) as exc:
    conclusion = final_run_status_check(token, infra_repo, run_id, deadline_seconds=120)
    if conclusion is None:
        _update_cluster_in_state(bucket, target.name, ClusterState.DESTROY_FAILED)
        sys.exit(1)
```

Inside `final_run_status_check`, the same tenacity decoration as the primary fetch applies, and the call swallows its own transient and HTTP errors. The function returns `None` to signal "still indeterminate." A `None` return preserves the original failure transition. Any real conclusion (`success`, `failure`, `cancelled`, `timed_out`, `skipped`) drives the normal post-poll branch, including the success path that removes the cluster from pool state and cleans stage branches.

`DESTROY_FAILED` is a state distinct from `DESTROYING`. An operator can now tell "destroy in progress" from "destroy gave up." The bidirectional `DESTROY_FAILED <-> DESTROYING` transition in `VALID_TRANSITIONS` allows manual retry without fighting the state machine.

## How to Detect

This race is invisible in normal observation. On the GitHub side the workflow run reports `success`, yet the local pool state says `DESTROY_FAILED` and the local logs show a transient error. The diagnostic signal is the divergence between the actual run conclusion (visible in the Actions UI or via a manual `gh run view`) and the `pool-ctl` exit code.

When designing any polling-with-budget loop against a remote long-running operation, treat budget exhaustion and last-poll transient errors as indeterminate, not failed. One idempotent re-read against the same operation identifier, with a tight independent budget, must run before any state transition that asserts non-completion. The cost is one extra API call per release; the benefit is that a real `success` conclusion is never discarded by a flaky network at the end of the wait.
