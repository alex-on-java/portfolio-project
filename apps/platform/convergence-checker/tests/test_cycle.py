from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from convergence_checker.cycle import CycleConfig, run_cycle
from convergence_checker.io_adapters import NullStatusReporter
from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    CycleInputs,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)

# ---------------------------------------------------------------------------
# Fakes for run_cycle tests
# ---------------------------------------------------------------------------


@dataclass
class FakeClusterReader:
    identity: dict[str, str] = field(default_factory=dict)
    apps: list[ApplicationStatus] = field(default_factory=list)
    stage_namespaces: list[str] = field(default_factory=list)
    stages_by_namespace: dict[str, list[StageStatus]] = field(default_factory=dict)

    heartbeat_writes: list[datetime] = field(default_factory=list)
    list_stages_calls: list[str] = field(default_factory=list)

    raise_on_write_heartbeat: Exception | None = None

    def read_cluster_identity(self) -> dict[str, str]:
        return self.identity

    def list_applications(self) -> list[ApplicationStatus]:
        return list(self.apps)

    def list_stage_namespaces(self) -> list[str]:
        return list(self.stage_namespaces)

    def list_stages(self, namespace: str) -> list[StageStatus]:
        self.list_stages_calls.append(namespace)
        return list(self.stages_by_namespace.get(namespace, []))

    def write_heartbeat(self, now: datetime) -> None:
        if self.raise_on_write_heartbeat is not None:
            raise self.raise_on_write_heartbeat
        self.heartbeat_writes.append(now)


@dataclass
class RecordingReporter:
    posts: list[dict[str, str]] = field(default_factory=list)
    raise_on_post: Exception | None = None

    def post(
        self,
        *,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None:
        if self.raise_on_post is not None:
            raise self.raise_on_post
        self.posts.append(
            {
                "owner_repo": owner_repo,
                "sha": sha,
                "state": state,
                "context": context,
                "description": description,
            },
        )


class RecordingNullReporter(NullStatusReporter):
    def __init__(self) -> None:
        super().__init__()
        self.posts: list[dict[str, str]] = []

    def post(
        self,
        *,
        owner_repo: str,
        sha: str,
        state: str,
        context: str,
        description: str,
    ) -> None:
        self.posts.append(
            {
                "owner_repo": owner_repo,
                "sha": sha,
                "state": state,
                "context": context,
                "description": description,
            },
        )


# ---------------------------------------------------------------------------
# Shared fixtures for run_cycle tests
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def config() -> CycleConfig:
    return CycleConfig(
        stability_threshold=3,
        safety_timeout_seconds=600,
        owner_repo="acme/repo",
        github_status_context="convergence",
    )


@pytest.fixture
def reader() -> FakeClusterReader:
    return FakeClusterReader(
        identity={"prCommitSha": "sha-A"},
        apps=[
            ApplicationStatus(
                name="web-app",
                health_status="Healthy",
                sync_status="Synced",
                operation_phase="Succeeded",
            ),
        ],
        stage_namespaces=["portfolio-project"],
        stages_by_namespace={
            "portfolio-project": [
                StageStatus(
                    name="workloads-web-app",
                    namespace="portfolio-project",
                    health_status="Healthy",
                    conditions={"Ready": True, "Healthy": True, "Verified": True},
                ),
            ],
        },
    )


@pytest.fixture
def reporter() -> RecordingReporter:
    return RecordingReporter()


@pytest.fixture
def base_inputs() -> CycleInputs:
    return CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit_sha="sha-A",
        previous_sent_status=None,
    )


@pytest.fixture
def stub_evaluator(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    handle: dict[str, Any] = {
        "verdict": EvaluationVerdict.HEALTHY,
        "description": "stub-healthy",
        "new_state": ConvergenceState(consecutive_healthy=3),
        "evaluate_app_calls": [],
        "evaluate_stage_calls": [],
        "aggregate_calls": [],
    }

    def fake_evaluate_app(app: ApplicationStatus) -> EvaluationResult:
        handle["evaluate_app_calls"].append(app)
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=f"app:{app.name}",
        )

    def fake_evaluate_stage(stage: StageStatus) -> EvaluationResult:
        handle["evaluate_stage_calls"].append(stage)
        return EvaluationResult(
            verdict=EvaluationVerdict.HEALTHY,
            description=f"stage:{stage.namespace}/{stage.name}",
        )

    def fake_aggregate(
        results: list[EvaluationResult],
        state: ConvergenceState,
        stability_threshold: int,
        safety_timeout_seconds: int,
    ) -> tuple[EvaluationResult, ConvergenceState]:
        handle["aggregate_calls"].append(
            {
                "results": results,
                "state": state,
                "stability_threshold": stability_threshold,
                "safety_timeout_seconds": safety_timeout_seconds,
            },
        )
        return (
            EvaluationResult(verdict=handle["verdict"], description=handle["description"]),
            handle["new_state"],
        )

    monkeypatch.setattr("convergence_checker.cycle.evaluator.evaluate_app", fake_evaluate_app)
    monkeypatch.setattr("convergence_checker.cycle.evaluator.evaluate_stage", fake_evaluate_stage)
    monkeypatch.setattr("convergence_checker.cycle.evaluator.aggregate", fake_aggregate)

    return handle


# ---------------------------------------------------------------------------
# run_cycle tests
# ---------------------------------------------------------------------------


class TestRunCycle:
    @pytest.fixture(autouse=True)
    def _autouse_stub_evaluator(self, stub_evaluator: dict[str, Any]) -> dict[str, Any]:
        return stub_evaluator

    def test_happy_path_returns_outputs_and_drives_side_effects(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        base_inputs: CycleInputs,
        stub_evaluator: dict[str, Any],
    ) -> None:
        outputs = run_cycle(base_inputs, reader, reporter, config, now=NOW)

        assert outputs.new_commit_sha == "sha-A"
        assert outputs.resource_count == 2
        assert outputs.new_state is stub_evaluator["new_state"]
        assert outputs.result.verdict == EvaluationVerdict.HEALTHY
        assert outputs.new_sent_status == ("success", "stub-healthy")

        assert reader.heartbeat_writes == [NOW]

        assert len(stub_evaluator["aggregate_calls"]) == 1
        assert stub_evaluator["aggregate_calls"][0]["stability_threshold"] == config.stability_threshold
        assert stub_evaluator["aggregate_calls"][0]["safety_timeout_seconds"] == config.safety_timeout_seconds

        assert len(reporter.posts) == 1
        assert reporter.posts[0]["state"] == "success"
        assert reporter.posts[0]["sha"] == "sha-A"
        assert reporter.posts[0]["owner_repo"] == config.owner_repo
        assert reporter.posts[0]["context"] == config.github_status_context

    def test_evaluator_called_once_per_resource_across_namespaces(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        base_inputs: CycleInputs,
        stub_evaluator: dict[str, Any],
    ) -> None:
        reader.apps = [
            ApplicationStatus(name="web-app", health_status="Healthy", sync_status="Synced"),
            ApplicationStatus(name="api-app", health_status="Healthy", sync_status="Synced"),
            ApplicationStatus(name="worker-app", health_status="Healthy", sync_status="Synced"),
        ]
        reader.stage_namespaces = ["ns-a", "ns-b"]
        reader.stages_by_namespace = {
            "ns-a": [
                StageStatus(name="stage-a1", namespace="ns-a", health_status="Healthy"),
                StageStatus(name="stage-a2", namespace="ns-a", health_status="Healthy"),
            ],
            "ns-b": [
                StageStatus(name="stage-b1", namespace="ns-b", health_status="Healthy"),
            ],
        }

        outputs = run_cycle(base_inputs, reader, reporter, config, now=NOW)

        assert outputs.resource_count == 6
        assert sorted(a.name for a in stub_evaluator["evaluate_app_calls"]) == sorted(
            ["web-app", "api-app", "worker-app"],
        )
        assert sorted((s.namespace, s.name) for s in stub_evaluator["evaluate_stage_calls"]) == sorted(
            [
                ("ns-a", "stage-a1"),
                ("ns-a", "stage-a2"),
                ("ns-b", "stage-b1"),
            ],
        )
        assert sorted(reader.list_stages_calls) == sorted(["ns-a", "ns-b"])
        assert len(stub_evaluator["aggregate_calls"]) == 1
        assert len(stub_evaluator["aggregate_calls"][0]["results"]) == 6

    def test_sha_change_resets_state_and_clears_dedup_memory(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        stub_evaluator: dict[str, Any],
    ) -> None:
        reader.identity = {"prCommitSha": "sha-B"}
        inputs = CycleInputs(
            previous_state=ConvergenceState(consecutive_healthy=4),
            previous_commit_sha="sha-A",
            previous_sent_status=("success", "stub-healthy"),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert outputs.new_commit_sha == "sha-B"

        passed_state = stub_evaluator["aggregate_calls"][0]["state"]
        assert passed_state.consecutive_healthy == 0

        assert len(reporter.posts) == 1
        assert reporter.posts[0]["sha"] == "sha-B"

    def test_same_sha_with_unchanged_status_skips_post(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        stub_evaluator: dict[str, Any],
    ) -> None:
        stub_evaluator["verdict"] = EvaluationVerdict.HEALTHY
        stub_evaluator["description"] = "All healthy"
        inputs = CycleInputs(
            previous_state=ConvergenceState(),
            previous_commit_sha="sha-A",
            previous_sent_status=("success", "All healthy"),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert reporter.posts == []
        assert outputs.new_sent_status == ("success", "All healthy")

    def test_null_reporter_skips_post_even_with_valid_sha(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        base_inputs: CycleInputs,
    ) -> None:
        null_reporter = RecordingNullReporter()

        outputs = run_cycle(base_inputs, reader, null_reporter, config, now=NOW)

        assert null_reporter.posts == []
        assert outputs.new_sent_status is None

    def test_missing_pr_sha_skips_post_but_still_writes_heartbeat(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
    ) -> None:
        reader.identity = {}
        inputs = CycleInputs(
            previous_state=ConvergenceState(),
            previous_commit_sha=None,
            previous_sent_status=None,
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert reporter.posts == []
        assert outputs.new_commit_sha is None
        assert len(reader.heartbeat_writes) == 1

    def test_reporter_post_exception_is_swallowed_and_dedup_memory_unchanged(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
    ) -> None:
        reporter.raise_on_post = RuntimeError("github 500")
        inputs = CycleInputs(
            previous_state=ConvergenceState(),
            previous_commit_sha="sha-A",
            previous_sent_status=("pending", "earlier"),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert outputs.new_sent_status == ("pending", "earlier")
        assert reader.heartbeat_writes == [NOW]

    def test_heartbeat_failure_is_swallowed_and_returns_outputs(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        base_inputs: CycleInputs,
        stub_evaluator: dict[str, Any],
    ) -> None:
        reader.raise_on_write_heartbeat = RuntimeError("k8s heartbeat write failed")

        outputs = run_cycle(base_inputs, reader, reporter, config, now=NOW)

        assert reader.heartbeat_writes == []
        assert outputs.new_state is stub_evaluator["new_state"]
