from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from convergence_checker.core.cycle import CycleConfig
from convergence_checker.core.models import (
    ApplicationStatus,
    ClusterIdentity,
    ConvergenceState,
    CycleInputs,
    CycleOutputs,
    EvaluationResult,
    EvaluationVerdict,
    NoCommit,
    StageStatus,
)
from convergence_checker.infrastructure import runner
from convergence_checker.infrastructure.github.adapters import NullStatusReporter
from convergence_checker.infrastructure.runner import LoopPacing
from tests.factories import healthy_streak, known_commit, no_sent_status, sent_status

if TYPE_CHECKING:
    from collections.abc import Callable

    from convergence_checker.core.ports import ClusterReader, StatusReporter


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
    sha: str = "sha-A",
    new_state: ConvergenceState | None = None,
    new_sent: str | None = None,
) -> CycleOutputs:
    return CycleOutputs(
        new_state=new_state if new_state is not None else healthy_streak(),
        new_commit=known_commit(sha),
        new_sent_status=sent_status("success", new_sent) if new_sent is not None else no_sent_status(),
        result=EvaluationResult(verdict=EvaluationVerdict.HEALTHY, description="ok"),
        resource_count=1,
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


FIXED_NOW = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)


class _NoopReader:
    def read_cluster_identity(self) -> ClusterIdentity:
        return ClusterIdentity(argocd_namespace="argocd", commit=NoCommit(reason="test"))

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
        previous_state=healthy_streak(),
        previous_commit=known_commit("sha-A"),
        previous_sent_status=no_sent_status(),
    )


@pytest.fixture
def cycle_stub(monkeypatch: pytest.MonkeyPatch) -> CycleStub:
    stub = CycleStub()
    monkeypatch.setattr("convergence_checker.core.cycle.run_cycle", stub)
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

        runner.run_until(
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

        runner.run_until(
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

        runner.run_until(
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
            new_state=healthy_streak(2),
            new_sent="first",
        )
        second = _make_output(
            sha="sha-B",
            new_state=healthy_streak(3),
            new_sent="second",
        )
        cycle_stub.scripted = [first, second]

        runner.run_until(
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
        assert cycle2_inputs.previous_commit == first.new_commit
        assert cycle2_inputs.previous_sent_status == first.new_sent_status

    def test_exception_in_cycle_propagates_loudly(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [RuntimeError("transient cluster read failure")]

        with pytest.raises(RuntimeError, match="transient cluster read failure"):
            runner.run_until(
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

        assert len(cycle_stub.calls) == 1

    def test_exception_in_cycle_skips_sleep(
        self,
        cycle_stub: CycleStub,
        reporter: NullStatusReporter,
        config: CycleConfig,
        base_inputs: CycleInputs,
        constant_clock: Callable[[], datetime],
    ) -> None:
        cycle_stub.scripted = [RuntimeError("boom")]
        sleep = RecordingSleep()

        with pytest.raises(RuntimeError, match="boom"):
            runner.run_until(
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

        assert sleep.intervals == []

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

        runner.run_until(
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
