from __future__ import annotations

from datetime import UTC, datetime

from convergence_checker.cycle import reconcile_startup_state
from convergence_checker.models import ConvergenceState


class TestStartupStateReconciliation:
    def test_startup_resets_state_on_sha_mismatch(self) -> None:
        loaded = ConvergenceState(
            consecutive_healthy=4,
            first_pending_at=datetime.now(tz=UTC),
            last_commit_sha="old_sha",
        )
        result = reconcile_startup_state(loaded, "new_sha")
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
        result = reconcile_startup_state(loaded, "same_sha")
        assert result.last_commit_sha == "same_sha"
        assert result.consecutive_healthy == 3
        assert result.first_pending_at == now

    def test_startup_resets_when_loaded_sha_is_none_and_current_is_set(self) -> None:
        loaded = ConvergenceState(consecutive_healthy=2, last_commit_sha=None)
        result = reconcile_startup_state(loaded, "new_sha")
        assert result.last_commit_sha == "new_sha"
        assert result.consecutive_healthy == 0

    def test_startup_resets_when_loaded_sha_is_set_and_current_is_none(self) -> None:
        loaded = ConvergenceState(consecutive_healthy=2, last_commit_sha="old_sha")
        result = reconcile_startup_state(loaded, None)
        assert result.last_commit_sha is None
        assert result.consecutive_healthy == 0
