from __future__ import annotations

from datetime import UTC, datetime, timedelta

from convergence_checker.core.evaluator import (
    aggregate,
    evaluate_app,
    evaluate_stage,
)
from convergence_checker.core.models import (
    ApplicationStatus,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)
from tests.factories import app_status, healthy_streak, pending_since, stage_status


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
        app = app_status(
            name="test",
            health="Healthy",
            sync="OutOfSync",
            operation="Succeeded",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_missing_outofsync(self) -> None:
        app = app_status(
            name="test",
            health="Missing",
            sync="OutOfSync",
            operation=None,
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_operation_failed(self) -> None:
        app = app_status(
            name="test",
            health="Healthy",
            sync="Synced",
            operation="Failed",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_operation_error(self) -> None:
        app = app_status(
            name="test",
            health="Progressing",
            sync="Synced",
            operation="Error",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_degraded_takes_precedence_over_failed_operation(self) -> None:
        app = app_status(
            name="test",
            health="Degraded",
            sync="OutOfSync",
            operation="Failed",
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "Degraded" in result.description

    def test_healthy_synced_no_operation(self) -> None:
        app = app_status(
            name="test",
            health="Healthy",
            sync="Synced",
            operation=None,
        )
        result = evaluate_app(app)
        assert result.verdict == EvaluationVerdict.HEALTHY

    def test_all_none(self) -> None:
        app = app_status(name="test", health=None, sync=None, operation=None)
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
        stage = stage_status(
            name="test",
            namespace="ns",
            health="Healthy",
            conditions={"Ready": True, "Healthy": False, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.FAILURE

    def test_verified_false(self) -> None:
        stage = stage_status(
            name="test",
            namespace="ns",
            health="Healthy",
            conditions={"Ready": True, "Healthy": True, "Verified": False},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_missing_conditions(self) -> None:
        stage = stage_status(
            name="test",
            namespace="ns",
            health="Healthy",
            conditions={},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_no_health_status(self) -> None:
        stage = stage_status(
            name="test",
            namespace="ns",
            health=None,
            conditions={"Ready": True, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_ready_false(self) -> None:
        stage = stage_status(
            name="test",
            namespace="ns",
            health="Healthy",
            conditions={"Ready": False, "Healthy": True, "Verified": True},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.PENDING

    def test_unhealthy_takes_precedence_over_healthy_condition_false(self) -> None:
        stage = stage_status(
            name="test",
            namespace="ns",
            health="Unhealthy",
            conditions={"Healthy": False},
        )
        result = evaluate_stage(stage)
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "Unhealthy" in result.description


class TestAggregate:
    _now = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)

    def _healthy(self, name: str = "ok") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.HEALTHY, description=name)

    def _pending(self, name: str = "wait") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.PENDING, description=name)

    def _failure(self, name: str = "broken") -> EvaluationResult:
        return EvaluationResult(verdict=EvaluationVerdict.FAILURE, description=name)

    def test_five_consecutive_healthy_is_success(self) -> None:
        state = healthy_streak(4)
        result, new_state = aggregate(
            [self._healthy()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.HEALTHY
        assert new_state.consecutive_healthy == 5

    def test_four_healthy_then_pending_resets(self) -> None:
        state = healthy_streak(4)
        result, new_state = aggregate(
            [self._healthy(), self._pending()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_failure_is_immediate(self) -> None:
        state = healthy_streak(4)
        result, new_state = aggregate(
            [self._failure()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.FAILURE
        assert new_state.consecutive_healthy == 0

    def test_mixed_results_are_pending(self) -> None:
        state = healthy_streak()
        result, new_state = aggregate(
            [self._healthy(), self._pending()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_safety_timeout(self) -> None:
        old_time = self._now - timedelta(seconds=1000)
        state = pending_since(old_time)
        result, _ = aggregate(
            [self._pending()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "timeout" in result.description.lower()

    def test_pending_within_timeout(self) -> None:
        recent = self._now - timedelta(seconds=60)
        state = pending_since(recent)
        result, new_state = aggregate(
            [self._pending()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.pending_since() == recent

    def test_first_pending_sets_timestamp(self) -> None:
        state = healthy_streak()
        _, new_state = aggregate(
            [self._pending()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert new_state.phase == "pending"
        assert new_state.pending_since() == self._now

    def test_healthy_clears_pending_timestamp(self) -> None:
        state = pending_since(self._now)
        _, new_state = aggregate(
            [self._healthy()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert new_state.phase == "healthy_streak"

    def test_empty_results_stay_pending(self) -> None:
        state = healthy_streak()
        result, new_state = aggregate([], state, stability_threshold=5, safety_timeout_seconds=900, now=self._now)
        assert result.verdict == EvaluationVerdict.PENDING
        assert new_state.consecutive_healthy == 0

    def test_multiple_failures_all_reported(self) -> None:
        state = healthy_streak()
        result, _ = aggregate(
            [self._failure("a"), self._failure("b")],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert result.verdict == EvaluationVerdict.FAILURE
        assert "a" in result.description
        assert "b" in result.description

    def test_consecutive_healthy_caps_at_threshold_times_two(self) -> None:
        state = healthy_streak(10)
        _, new_state = aggregate(
            [self._healthy()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert new_state.consecutive_healthy == 10

    def test_consecutive_healthy_reaches_cap_then_stops(self) -> None:
        state = healthy_streak(9)
        _, mid_state = aggregate(
            [self._healthy()],
            state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert mid_state.consecutive_healthy == 10
        _, capped_state = aggregate(
            [self._healthy()],
            mid_state,
            stability_threshold=5,
            safety_timeout_seconds=900,
            now=self._now,
        )
        assert capped_state.consecutive_healthy == 10
