from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from convergence_checker import loop
from convergence_checker.cycle import CycleConfig
from convergence_checker.io_adapters import ClusterReader, NullStatusReporter, StatusReporter
from convergence_checker.loop import LoopPacing
from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    CycleInputs,
    CycleOutputs,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)

if TYPE_CHECKING:
    from collections.abc import Callable


# ---------------------------------------------------------------------------
# Test doubles for run_until
# ---------------------------------------------------------------------------


@dataclass
class StopAfter:
    n: int
    calls: int = 0

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls <= self.n


@dataclass
class RecordingSleep:
    intervals: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        self.intervals.append(seconds)


@dataclass
class ScriptedClock:
    times: list[datetime]
    issued: list[datetime] = field(default_factory=list)

    def __call__(self) -> datetime:
        if not self.times:
            msg = "ScriptedClock exhausted"
            raise AssertionError(msg)
        t = self.times.pop(0)
        self.issued.append(t)
        return t


@dataclass
class CycleStub:
    scripted: list[CycleOutputs | Exception] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(
        self,
        inputs: CycleInputs,
        reader: ClusterReader,
        reporter: StatusReporter,
        config: CycleConfig,
        *,
        now: datetime,
    ) -> CycleOutputs:
        self.calls.append(
            {"inputs": inputs, "reader": reader, "reporter": reporter, "config": config, "now": now},
        )
        if not self.scripted:
            msg = "CycleStub has no scripted outcome for this call"
            raise AssertionError(msg)
        outcome = self.scripted.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_output(
    sha: str | None = "sha-A",
    new_state: ConvergenceState | None = None,
    new_sent: tuple[str, str] | None = None,
) -> CycleOutputs:
    return CycleOutputs(
        new_state=new_state if new_state is not None else ConvergenceState(),
        new_commit_sha=sha,
        new_sent_status=new_sent,
        result=EvaluationResult(verdict=EvaluationVerdict.HEALTHY, description="ok"),
        resource_count=1,
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


FIXED_NOW = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)


class _NoopReader:
    def read_cluster_identity(self) -> dict[str, str]:
        return {}

    def list_applications(self) -> list[ApplicationStatus]:
        return []

    def list_stage_namespaces(self) -> list[str]:
        return []

    def list_stages(self, _namespace: str) -> list[StageStatus]:
        return []

    def write_heartbeat(self, _now: datetime) -> None:
        return


SENTINEL_READER: ClusterReader = _NoopReader()


@pytest.fixture
def reporter() -> NullStatusReporter:
    return NullStatusReporter()


@pytest.fixture
def config() -> CycleConfig:
    return CycleConfig(
        stability_threshold=3,
        safety_timeout_seconds=600,
        owner_repo="acme/repo",
        github_status_context="convergence",
    )


@pytest.fixture
def base_inputs() -> CycleInputs:
    return CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit_sha="sha-A",
        previous_sent_status=None,
    )


@pytest.fixture
def cycle_stub(monkeypatch: pytest.MonkeyPatch) -> CycleStub:
    stub = CycleStub()
    monkeypatch.setattr("convergence_checker.cycle.run_cycle", stub)
    return stub


@pytest.fixture
def constant_clock() -> Callable[[], datetime]:
    return lambda: FIXED_NOW


# ---------------------------------------------------------------------------
# run_until tests
# ---------------------------------------------------------------------------


class TestRunUntil:
    def test_iteration_count_matches_should_continue(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [_make_output() for _ in range(3)]
        sleep = RecordingSleep()
        stop = StopAfter(n=3)

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=sleep,
                clock=constant_clock,
                should_continue=stop,
                interval_seconds=0.0,
            ),
        )

        assert len(cycle_stub.calls) == 3
        assert sleep.intervals == [0.0, 0.0, 0.0]
        assert stop.calls == 4

    def test_zero_iterations_when_should_continue_is_false_initially(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        sleep = RecordingSleep()

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=sleep,
                clock=constant_clock,
                should_continue=lambda: False,
                interval_seconds=0.0,
            ),
        )

        assert cycle_stub.calls == []
        assert sleep.intervals == []

    def test_initial_inputs_used_for_first_call(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [_make_output()]

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=RecordingSleep(),
                clock=constant_clock,
                should_continue=StopAfter(n=1),
                interval_seconds=0.0,
            ),
        )

        assert cycle_stub.calls[0]["inputs"] is base_inputs
        assert cycle_stub.calls[0]["reader"] is SENTINEL_READER
        assert cycle_stub.calls[0]["reporter"] is reporter
        assert cycle_stub.calls[0]["config"] is config

    def test_outputs_are_threaded_into_next_iteration_inputs(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        first = _make_output(
            sha="sha-B",
            new_state=ConvergenceState(consecutive_healthy=2),
            new_sent=("success", "first"),
        )
        second = _make_output(
            sha="sha-B",
            new_state=ConvergenceState(consecutive_healthy=3),
            new_sent=("success", "second"),
        )
        cycle_stub.scripted = [first, second]

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=RecordingSleep(),
                clock=constant_clock,
                should_continue=StopAfter(n=2),
                interval_seconds=0.0,
            ),
        )

        cycle2_inputs = cycle_stub.calls[1]["inputs"]
        assert cycle2_inputs.previous_state == first.new_state
        assert cycle2_inputs.previous_commit_sha == first.new_commit_sha
        assert cycle2_inputs.previous_sent_status == first.new_sent_status

    def test_exception_in_cycle_is_swallowed_loop_continues_inputs_unchanged(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        ok_output = _make_output(
            sha="sha-A",
            new_state=ConvergenceState(consecutive_healthy=1),
            new_sent=("success", "ok"),
        )
        cycle_stub.scripted = [
            ok_output,
            RuntimeError("transient cluster read failure"),
            _make_output(sha="sha-A", new_state=ConvergenceState(consecutive_healthy=2)),
        ]

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=RecordingSleep(),
                clock=constant_clock,
                should_continue=StopAfter(n=3),
                interval_seconds=0.0,
            ),
        )

        assert len(cycle_stub.calls) == 3

        cycle3_inputs = cycle_stub.calls[2]["inputs"]
        assert cycle3_inputs.previous_state == ok_output.new_state
        assert cycle3_inputs.previous_commit_sha == ok_output.new_commit_sha
        assert cycle3_inputs.previous_sent_status == ok_output.new_sent_status

    def test_sleep_runs_once_per_iteration_including_after_exception(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [
            RuntimeError("boom"),
            _make_output(),
        ]
        sleep = RecordingSleep()

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=sleep,
                clock=constant_clock,
                should_continue=StopAfter(n=2),
                interval_seconds=12.5,
            ),
        )

        assert sleep.intervals == [12.5, 12.5]

    def test_clock_called_per_cycle_value_passed_as_now(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
    ) -> None:
        cycle_stub.scripted = [_make_output(), _make_output()]
        t0 = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
        t1 = datetime(2026, 4, 26, 12, 0, 12, tzinfo=UTC)
        clock = ScriptedClock(times=[t0, t1])

        loop.run_until(
            initial_inputs=base_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=RecordingSleep(),
                clock=clock,
                should_continue=StopAfter(n=2),
                interval_seconds=0.0,
            ),
        )

        assert cycle_stub.calls[0]["now"] == t0
        assert cycle_stub.calls[1]["now"] == t1
        assert clock.issued == [t0, t1]

    def test_dry_run_flag_persists_across_iterations(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [_make_output(), _make_output()]
        dry_run_inputs = CycleInputs(
            previous_state=ConvergenceState(),
            previous_commit_sha="sha-A",
            previous_sent_status=None,
            dry_run=True,
        )

        loop.run_until(
            initial_inputs=dry_run_inputs,
            reader=SENTINEL_READER,
            reporter=reporter,
            config=config,
            pacing=LoopPacing(
                sleep=RecordingSleep(),
                clock=constant_clock,
                should_continue=StopAfter(n=2),
                interval_seconds=0.0,
            ),
        )

        assert cycle_stub.calls[1]["inputs"].dry_run is True
