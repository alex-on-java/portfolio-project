from __future__ import annotations

from datetime import UTC, datetime, timedelta

from convergence_checker.evaluator import (
    aggregate,
    evaluate_app,
    evaluate_stage,
)
from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)


class TestEvaluateApp:
    def test_healthy_synced_succeeded(self, healthy_synced_app: ApplicationStatus) -> None:
        result = evaluate_app(healthy_synced_app)
        assert result.verdict == EvaluationVerdict.HEALTHY

    def test_degraded(self, degraded_app: ApplicationStatus) -> None:
        result = evaluate_app(degraded_app)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_progressing_outofsync_running(self, progressing_app: ApplicationStatus) -> None:
        result = evaluate_app(progressing_app)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_healthy_outofsync(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Healthy",
            sync_status="OutOfSync",
            operation_phase="Succeeded",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_missing_outofsync(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Missing",
            sync_status="OutOfSync",
            operation_phase=None,
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_operation_failed(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Healthy",
            sync_status="Synced",
            operation_phase="Failed",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_operation_error(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Progressing",
            sync_status="Synced",
            operation_phase="Error",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_degraded_takes_precedence_over_failed_operation(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Degraded",
            sync_status="OutOfSync",
            operation_phase="Failed",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "Degraded" in result.description

    def test_healthy_synced_no_operation(self) -> None:
        app = ApplicationStatus(
            name="test",
            health_status="Healthy",
            sync_status="Synced",
            operation_phase=None,
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.HEALTHY

    def test_all_none(self) -> None:
        app = ApplicationStatus(name="test")
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.PENDING


class TestEvaluateStage:
    def test_healthy_ready_verified(self, healthy_stage: StageStatus) -> None:
        result = evaluate_stage(healthy_stage)
        assert result.verdict == EvaluationVerdict.HEALTHY

    def test_unhealthy(self, unhealthy_stage: StageStatus) -> None:
        result = evaluate_stage(unhealthy_stage)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_healthy_condition_false(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status="Healthy",
            conditions={"Ready": True, "Healthy": False, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_verified_false(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status="Healthy",
            conditions={"Ready": True, "Healthy": True, "Verified": False},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_missing_conditions(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status="Healthy",
            conditions={},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_no_health_status(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status=None,
            conditions={"Ready": True, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_ready_false(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status="Healthy",
            conditions={"Ready": False, "Healthy": True, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_unhealthy_takes_precedence_over_healthy_condition_false(self) -> None:
        stage = StageStatus(
            name="test",
            namespace="ns",
            health_status="Unhealthy",
            conditions={"Healthy": False},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "Unhealthy" in result.description


class TestAggregate:
    def _healthy(self, name: str = "ok") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.HEALTHY, description=name)

    def _pending(self, name: str = "wait") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.PENDING, description=name)

    def _failure(self, name: str = "broken") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.FAILURE, description=name)

    def test_five_consecutive_healthy_is_success(self) -> None:
        state = ConvergenceState(consecutive_healthy=4)
        result, new_state = aggregate([self._healthy()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert result.verdict == EvaluationVerdict.HEALTHY
        assert new_state.consecutive_healthy == 5

    def test_four_healthy_then_pending_resets(self) -> None:
        state = ConvergenceState(consecutive_healthy=4)
        result, new_state = aggregate(
            [self._healthy(), self._pending()], state, stability_threshold=5, safety_timeout_seconds=900
        )
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_failure_is_immediate(self) -> None:
        state = ConvergenceState(consecutive_healthy=4)
        result, new_state = aggregate([self._failure()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert new_state.consecutive_healthy == 0

    def test_mixed_results_are_pending(self) -> None:
        state = ConvergenceState()
        result, new_state = aggregate(
            [self._healthy(), self._pending()], state, stability_threshold=5, safety_timeout_seconds=900
        )
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_safety_timeout(self) -> None:
        old_time = datetime.now(tz=UTC) - timedelta(seconds=1000)
        state = ConvergenceState(first_pending_at=old_time)
        result, _ = aggregate([self._pending()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "timeout" in result.description.lower()

    def test_pending_within_timeout(self) -> None:
        recent = datetime.now(tz=UTC) - timedelta(seconds=60)
        state = ConvergenceState(first_pending_at=recent)
        result, new_state = aggregate([self._pending()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.first_pending_at == recent

    def test_first_pending_sets_timestamp(self) -> None:
        state = ConvergenceState()
        _, new_state = aggregate([self._pending()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert new_state.first_pending_at is not None

    def test_healthy_clears_pending_timestamp(self) -> None:
        state = ConvergenceState(first_pending_at=datetime.now(tz=UTC), consecutive_healthy=0)
        _, new_state = aggregate([self._healthy()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert new_state.first_pending_at is None

    def test_empty_results_stay_pending(self) -> None:
        state = ConvergenceState()
        result, new_state = aggregate([], state, stability_threshold=5, safety_timeout_seconds=900)
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_multiple_failures_all_reported(self) -> None:
        state = ConvergenceState()
        result, _ = aggregate(
            [self._failure("a"), self._failure("b")], state, stability_threshold=5, safety_timeout_seconds=900
        )
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "a" in result.description
        assert "b" in result.description

    def test_preserves_last_commit_sha(self) -> None:
        state = ConvergenceState(last_commit_sha="abc123")
        _, new_state = aggregate([self._healthy()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert new_state.last_commit_sha == "abc123"

    def test_consecutive_healthy_caps_at_threshold_times_two(self) -> None:
        state = ConvergenceState(consecutive_healthy=10)
        _, new_state = aggregate([self._healthy()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert new_state.consecutive_healthy == 10

    def test_consecutive_healthy_reaches_cap_then_stops(self) -> None:
        state = ConvergenceState(consecutive_healthy=9)
        _, mid_state = aggregate([self._healthy()], state, stability_threshold=5, safety_timeout_seconds=900)
        assert mid_state.consecutive_healthy == 10
        _, capped_state = aggregate([self._healthy()], mid_state, stability_threshold=5, safety_timeout_seconds=900)
        assert capped_state.consecutive_healthy == 10
