from __future__ import annotations

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
