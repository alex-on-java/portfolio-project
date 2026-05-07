from __future__ import annotations

from datetime import UTC, datetime, timedelta

from convergence_checker.domain import (
    ApplicationSnapshot,
    ConvergenceState,
    PostedStatus,
    ResourceState,
    StageSnapshot,
    classify_application,
    classify_stage,
    evaluate_summary,
    should_post_status,
    summarize_resources,
    truncate_description,
)


def test_degraded_application_is_broken_before_operation_phase() -> None:
    classification = classify_application(
        ApplicationSnapshot(name="app-a", health="Degraded", sync="Synced", operation="Failed"),
    )

    assert classification.state == ResourceState.BROKEN
    assert classification.description == "app-a: Degraded"


def test_failed_application_operation_is_broken_even_when_healthy() -> None:
    classification = classify_application(
        ApplicationSnapshot(name="app-a", health="Healthy", sync="Synced", operation="Error"),
    )

    assert classification.state == ResourceState.BROKEN
    assert classification.description == "app-a: operation Error"


def test_application_needs_healthy_and_synced_to_converge() -> None:
    converged = classify_application(
        ApplicationSnapshot(name="app-a", health="Healthy", sync="Synced", operation="Succeeded"),
    )
    missing_status = classify_application(ApplicationSnapshot(name="app-b", health=None, sync=None, operation=None))

    assert converged.state == ResourceState.CONVERGED
    assert converged.description == "app-a: Healthy+Synced"
    assert missing_status.state == ResourceState.IN_PROGRESS
    assert missing_status.description == "app-b: health=null sync=null op=null"


def test_stage_classification_uses_health_conditions_and_verified_readiness() -> None:
    converged = classify_stage(
        StageSnapshot(
            namespace="project-a",
            name="stage-a",
            health="Healthy",
            healthy_condition=True,
            ready_condition=True,
            verified_condition=True,
        ),
    )
    unverified = classify_stage(
        StageSnapshot(
            namespace="project-a",
            name="stage-a",
            health="Healthy",
            healthy_condition=True,
            ready_condition=True,
            verified_condition=None,
        ),
    )
    condition_failed = classify_stage(
        StageSnapshot(
            namespace="project-a",
            name="stage-a",
            health="Healthy",
            healthy_condition=False,
            ready_condition=True,
            verified_condition=True,
        ),
    )
    unhealthy = classify_stage(
        StageSnapshot(
            namespace="project-a",
            name="stage-a",
            health="Unhealthy",
            healthy_condition=True,
            ready_condition=True,
            verified_condition=True,
        ),
    )

    assert converged.state == ResourceState.CONVERGED
    assert converged.description == "project-a/stage-a: Healthy+Ready+Verified"
    assert unverified.state == ResourceState.IN_PROGRESS
    assert unverified.description == "project-a/stage-a: health=Healthy ready=true verified=null"
    assert condition_failed.state == ResourceState.BROKEN
    assert condition_failed.description == "project-a/stage-a: Healthy condition is False"
    assert unhealthy.state == ResourceState.BROKEN
    assert unhealthy.description == "project-a/stage-a: Unhealthy"


def test_broken_resources_win_aggregation_and_descriptions_are_deterministic() -> None:
    resources = (
        classify_stage(
            StageSnapshot(
                namespace="project-b",
                name="stage-b",
                health="Healthy",
                healthy_condition=True,
                ready_condition=False,
                verified_condition=True,
            ),
        ),
        classify_application(ApplicationSnapshot("app-b", "Healthy", "Synced", "Succeeded")),
        classify_application(ApplicationSnapshot("app-a", "Degraded", "OutOfSync", None)),
        classify_stage(
            StageSnapshot(
                namespace="project-a",
                name="stage-a",
                health="Unhealthy",
                healthy_condition=True,
                ready_condition=True,
                verified_condition=True,
            ),
        ),
    )

    summary = summarize_resources(resources)
    result, state = evaluate_summary(
        summary=summary,
        previous=ConvergenceState(last_seen_sha="sha-a"),
        observed_at=datetime(2026, 5, 7, tzinfo=UTC),
        stability_threshold=5,
        safety_timeout_seconds=900,
    )

    assert state.consecutive_converged == 0
    assert result.github_state == "failure"
    assert result.description == "Failed: app-a: Degraded; project-a/stage-a: Unhealthy"


def test_all_converged_requires_stability_threshold_and_counter_caps() -> None:
    summary = summarize_resources(
        (
            classify_application(ApplicationSnapshot("app-a", "Healthy", "Synced", "Succeeded")),
            classify_stage(
                StageSnapshot(
                    namespace="project-a",
                    name="stage-a",
                    health="Healthy",
                    healthy_condition=True,
                    ready_condition=True,
                    verified_condition=True,
                ),
            ),
        ),
    )
    state = ConvergenceState(last_seen_sha="sha-a")
    observed_at = datetime(2026, 5, 7, tzinfo=UTC)

    for count in range(1, 12):
        result, state = evaluate_summary(
            summary=summary,
            previous=state,
            observed_at=observed_at + timedelta(seconds=count),
            stability_threshold=5,
            safety_timeout_seconds=900,
        )

    assert state.consecutive_converged == 10
    assert result.github_state == "success"
    assert result.description == "All 2 resources healthy for 10 consecutive checks"


def test_first_all_converged_checks_post_pending_until_threshold() -> None:
    summary = summarize_resources((classify_application(ApplicationSnapshot("app-a", "Healthy", "Synced", None)),))

    result, state = evaluate_summary(
        summary=summary,
        previous=ConvergenceState(last_seen_sha="sha-a"),
        observed_at=datetime(2026, 5, 7, tzinfo=UTC),
        stability_threshold=2,
        safety_timeout_seconds=900,
    )

    assert state.consecutive_converged == 1
    assert result.github_state == "pending"
    assert result.description == "Healthy 1/2 — awaiting stability"


def test_in_progress_resets_counter_and_times_out_strictly_after_limit() -> None:
    summary = summarize_resources((classify_application(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None)),))
    first_seen_at = datetime(2026, 5, 7, tzinfo=UTC)
    state = ConvergenceState(consecutive_converged=4, first_in_progress_at=first_seen_at, last_seen_sha="sha-a")

    at_limit, state = evaluate_summary(
        summary=summary,
        previous=state,
        observed_at=first_seen_at + timedelta(seconds=900),
        stability_threshold=5,
        safety_timeout_seconds=900,
    )
    after_limit, state = evaluate_summary(
        summary=summary,
        previous=state,
        observed_at=first_seen_at + timedelta(seconds=901),
        stability_threshold=5,
        safety_timeout_seconds=900,
    )

    assert state.consecutive_converged == 0
    assert at_limit.github_state == "pending"
    assert at_limit.description == "1 resources pending"
    assert after_limit.github_state == "failure"
    assert after_limit.description == (
        "Safety timeout (900s) exceeded. Pending: app-a: health=Healthy sync=OutOfSync op=null"
    )


def test_empty_resource_set_advances_stability_counter() -> None:
    summary = summarize_resources(())

    result, state = evaluate_summary(
        summary=summary,
        previous=ConvergenceState(last_seen_sha="sha-a"),
        observed_at=datetime(2026, 5, 7, tzinfo=UTC),
        stability_threshold=1,
        safety_timeout_seconds=900,
    )

    assert state.consecutive_converged == 1
    assert result.github_state == "success"
    assert result.description == "All 0 resources healthy for 1 consecutive checks"


def test_sha_change_resets_cycle_state_and_post_memory() -> None:
    previous = ConvergenceState(
        consecutive_converged=5,
        first_in_progress_at=datetime(2026, 5, 7, tzinfo=UTC),
        last_posted=PostedStatus(sha="sha-a", state="success", description="old"),
        last_seen_sha="sha-a",
    )

    assert previous.with_sha("sha-a") == previous
    assert previous.with_sha("sha-b") == ConvergenceState(last_seen_sha="sha-b")


def test_status_dedup_is_sha_state_and_description_scoped() -> None:
    state = ConvergenceState(
        last_posted=PostedStatus(sha="sha-a", state="pending", description="1 resources pending"),
        last_seen_sha="sha-a",
    )

    assert not should_post_status(state, "sha-a", "pending", "1 resources pending")
    assert should_post_status(state, "sha-a", "success", "All 1 resources healthy for 5 consecutive checks")
    assert should_post_status(state, "sha-b", "pending", "1 resources pending")
    assert not should_post_status(state, None, "pending", "1 resources pending")


def test_description_truncates_by_unicode_codepoint_without_ellipsis() -> None:
    description = "a" * 139 + "é" + "tail"

    assert truncate_description(description) == "a" * 139 + "é"
