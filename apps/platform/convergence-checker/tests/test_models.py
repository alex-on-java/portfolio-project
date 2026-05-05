from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from attrs.exceptions import FrozenInstanceError

from convergence_checker.core.models import (
    ConditionUnknown,
    ConvergenceState,
    HealthyStreak,
    PendingPeriod,
    ReportedStatus,
    StageStatus,
)
from tests.factories import stage_status


class TestConvergenceState:
    _now = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)

    def test_default_state_starts_with_empty_healthy_streak(self) -> None:
        state = ConvergenceState()

        assert state.progress == HealthyStreak(consecutive_checks=0)
        assert state.phase == "healthy_streak"
        assert state.consecutive_healthy == 0

    def test_record_healthy_increments_and_caps_streak(self) -> None:
        state = ConvergenceState(progress=HealthyStreak(consecutive_checks=9))

        new_state = state.record_healthy(stability_threshold=5)
        capped_state = new_state.record_healthy(stability_threshold=5)

        assert new_state.consecutive_healthy == 10
        assert capped_state.consecutive_healthy == 10

    def test_record_healthy_from_pending_starts_new_streak(self) -> None:
        state = ConvergenceState(progress=PendingPeriod(first_observed_at=self._now))

        new_state = state.record_healthy(stability_threshold=5)

        assert new_state.phase == "healthy_streak"
        assert new_state.consecutive_healthy == 1

    def test_record_pending_preserves_original_pending_timestamp(self) -> None:
        original = self._now - timedelta(seconds=30)
        state = ConvergenceState(progress=PendingPeriod(first_observed_at=original))

        new_state = state.record_pending(now=self._now)

        assert new_state.pending_since() == original

    def test_record_pending_sets_timestamp_when_streak_breaks(self) -> None:
        state = ConvergenceState(progress=HealthyStreak(consecutive_checks=4))

        new_state = state.record_pending(now=self._now)

        assert new_state.progress == PendingPeriod(first_observed_at=self._now)
        assert new_state.consecutive_healthy == 0

    def test_pending_timeout_uses_injected_now(self) -> None:
        state = ConvergenceState(progress=PendingPeriod(first_observed_at=self._now - timedelta(seconds=901)))

        assert state.pending_timed_out(now=self._now, safety_timeout_seconds=900) is True

    def test_pending_since_fails_for_non_pending_state(self) -> None:
        with pytest.raises(TypeError, match="not pending"):
            ConvergenceState().pending_since()


class TestDomainImmutability:
    def test_convergence_state_is_frozen(self) -> None:
        state = ConvergenceState()

        with pytest.raises(FrozenInstanceError):
            state.progress = PendingPeriod(first_observed_at=datetime.now(tz=UTC))

    def test_stage_conditions_are_immutable(self) -> None:
        stage = stage_status(health="Healthy", conditions={"Ready": True})

        with pytest.raises(TypeError):
            stage.conditions["Ready"] = ConditionUnknown(value="Unknown")


class TestStageStatus:
    def test_unknown_condition_is_distinct_from_missing_condition(self) -> None:
        stage = StageStatus(
            name="stage",
            namespace="ns",
            health_status=ReportedStatus(value="Healthy"),
            conditions={"Ready": ConditionUnknown(value="Unknown")},
        )

        assert stage.conditions["Ready"] == ConditionUnknown(value="Unknown")
        assert stage.pending_description() == "ns/stage: health=Healthy ready=Unknown verified=missing"
