from __future__ import annotations

from datetime import UTC, datetime

from convergence_checker.loop import _reconcile_startup_state
from convergence_checker.models import ConvergenceState


class TestShaChangeDetection:
    def test_sha_change_resets_counter(self) -> None:
        state = ConvergenceState(
            consecutive_healthy=4,
            last_commit_sha="old_sha",
        )
        new_sha = "new_sha"
        assert new_sha != state.last_commit_sha

        reset_state = ConvergenceState(last_commit_sha=new_sha)
        assert reset_state.consecutive_healthy == 0
        assert reset_state.first_pending_at is None
        assert reset_state.last_commit_sha == new_sha

    def test_same_sha_preserves_state(self) -> None:
        state = ConvergenceState(
            consecutive_healthy=3,
            last_commit_sha="same_sha",
        )
        assert state.last_commit_sha == "same_sha"
        assert state.consecutive_healthy == 3

    def test_none_sha_is_log_only(self) -> None:
        state = ConvergenceState(last_commit_sha=None)
        assert state.last_commit_sha is None


class TestStartupStateReconciliation:
    def test_startup_resets_state_on_sha_mismatch(self) -> None:
        loaded = ConvergenceState(
            consecutive_healthy=4,
            first_pending_at=datetime.now(tz=UTC),
            last_commit_sha="old_sha",
        )
        result = _reconcile_startup_state(loaded, "new_sha")
        assert result.last_commit_sha == "new_sha"
        assert result.consecutive_healthy == 0
        assert result.first_pending_at is None

    def test_startup_preserves_state_on_matching_sha(self) -> None:
        now = datetime.now(tz=UTC)
        loaded = ConvergenceState(
            consecutive_healthy=3,
            first_pending_at=now,
            last_commit_sha="same_sha",
        )
        result = _reconcile_startup_state(loaded, "same_sha")
        assert result.last_commit_sha == "same_sha"
        assert result.consecutive_healthy == 3
        assert result.first_pending_at == now

    def test_startup_resets_when_loaded_sha_is_none_and_current_is_set(self) -> None:
        loaded = ConvergenceState(consecutive_healthy=2, last_commit_sha=None)
        result = _reconcile_startup_state(loaded, "new_sha")
        assert result.last_commit_sha == "new_sha"
        assert result.consecutive_healthy == 0

    def test_startup_resets_when_loaded_sha_is_set_and_current_is_none(self) -> None:
        loaded = ConvergenceState(consecutive_healthy=2, last_commit_sha="old_sha")
        result = _reconcile_startup_state(loaded, None)
        assert result.last_commit_sha is None
        assert result.consecutive_healthy == 0


class TestConvergenceStateRoundTrip:
    def test_json_roundtrip(self) -> None:
        state = ConvergenceState(
            consecutive_healthy=3,
            last_commit_sha="abc123",
        )
        json_str = state.model_dump_json()
        restored = ConvergenceState.model_validate_json(json_str)
        assert restored.consecutive_healthy == state.consecutive_healthy
        assert restored.last_commit_sha == state.last_commit_sha
        assert restored.first_pending_at == state.first_pending_at
