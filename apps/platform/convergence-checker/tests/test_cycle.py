from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from convergence_checker.core.cycle import CycleConfig, run_cycle
from convergence_checker.core.models import (
    ApplicationStatus,
    ClusterIdentity,
    ConvergenceState,
    CycleInputs,
    EvaluationResult,
    EvaluationVerdict,
    NoCommit,
    StageStatus,
)
from convergence_checker.infrastructure.github.adapters import NullStatusReporter
from tests.factories import (
    app_status,
    healthy_streak,
    known_commit,
    no_commit,
    no_sent_status,
    sent_status,
    stage_status,
)

if TYPE_CHECKING:
    from convergence_checker.core.ports import CommitStatus

# ---------------------------------------------------------------------------
# Fakes for run_cycle tests
# ---------------------------------------------------------------------------


@dataclass
class FakeClusterReader:
    identity: ClusterIdentity = field(
        default_factory=lambda: ClusterIdentity(argocd_namespace="argocd", commit=NoCommit(reason="test")),
    )
    apps: list[ApplicationStatus] = field(default_factory=list)
    stage_namespaces: list[str] = field(default_factory=list)
    stages_by_namespace: dict[str, list[StageStatus]] = field(default_factory=dict)

    heartbeat_writes: list[datetime] = field(default_factory=list)
    list_stages_calls: list[str] = field(default_factory=list)

    raise_on_write_heartbeat: Exception | None = None

    def read_cluster_identity(self) -> ClusterIdentity:
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
    posts: list[CommitStatus] = field(default_factory=list)
    raise_on_post: Exception | None = None

    def post(self, status: CommitStatus) -> None:
        if self.raise_on_post is not None:
            raise self.raise_on_post
        self.posts.append(status)


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
        identity=ClusterIdentity(argocd_namespace="argocd", commit=known_commit("sha-A")),
        apps=[
            app_status(
                name="web-app",
                health="Healthy",
                sync="Synced",
                operation="Succeeded",
            ),
        ],
        stage_namespaces=["portfolio-project"],
        stages_by_namespace={
            "portfolio-project": [
                stage_status(
                    name="workloads-web-app",
                    namespace="portfolio-project",
                    health="Healthy",
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
        previous_state=healthy_streak(),
        previous_commit=known_commit("sha-A"),
        previous_sent_status=no_sent_status(),
    )


@pytest.fixture
def stub_evaluator(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    handle: dict[str, Any] = {
        "verdict": EvaluationVerdict.HEALTHY,
        "description": "stub-healthy",
        "new_state": healthy_streak(3),
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
        *,
        now: datetime,
    ) -> tuple[EvaluationResult, ConvergenceState]:
        handle["aggregate_calls"].append(
            {
                "results": results,
                "state": state,
                "stability_threshold": stability_threshold,
                "safety_timeout_seconds": safety_timeout_seconds,
                "now": now,
            },
        )
        return (
            EvaluationResult(verdict=handle["verdict"], description=handle["description"]),
            handle["new_state"],
        )

    monkeypatch.setattr("convergence_checker.core.cycle.evaluator.evaluate_app", fake_evaluate_app)
    monkeypatch.setattr("convergence_checker.core.cycle.evaluator.evaluate_stage", fake_evaluate_stage)
    monkeypatch.setattr("convergence_checker.core.cycle.evaluator.aggregate", fake_aggregate)

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

        assert outputs.new_commit == known_commit("sha-A")
        assert outputs.resource_count == 2
        assert outputs.new_state is stub_evaluator["new_state"]
        assert outputs.result.verdict == EvaluationVerdict.HEALTHY
        assert outputs.new_sent_status == sent_status("success", "stub-healthy")

        assert reader.heartbeat_writes == [NOW]

        assert len(stub_evaluator["aggregate_calls"]) == 1
        assert stub_evaluator["aggregate_calls"][0]["stability_threshold"] == config.stability_threshold
        assert stub_evaluator["aggregate_calls"][0]["safety_timeout_seconds"] == config.safety_timeout_seconds
        assert stub_evaluator["aggregate_calls"][0]["now"] == NOW

        assert len(reporter.posts) == 1
        assert reporter.posts[0].state == "success"
        assert reporter.posts[0].sha == "sha-A"
        assert reporter.posts[0].owner_repo == config.owner_repo
        assert reporter.posts[0].context == config.github_status_context

    def test_evaluator_called_once_per_resource_across_namespaces(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        base_inputs: CycleInputs,
        stub_evaluator: dict[str, Any],
    ) -> None:
        reader.apps = [
            app_status(name="web-app", health="Healthy", sync="Synced", operation=None),
            app_status(name="api-app", health="Healthy", sync="Synced", operation=None),
            app_status(name="worker-app", health="Healthy", sync="Synced", operation=None),
        ]
        reader.stage_namespaces = ["ns-a", "ns-b"]
        reader.stages_by_namespace = {
            "ns-a": [
                stage_status(name="stage-a1", namespace="ns-a", health="Healthy"),
                stage_status(name="stage-a2", namespace="ns-a", health="Healthy"),
            ],
            "ns-b": [
                stage_status(name="stage-b1", namespace="ns-b", health="Healthy"),
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
        reader.identity = ClusterIdentity(argocd_namespace="argocd", commit=known_commit("sha-B"))
        inputs = CycleInputs(
            previous_state=healthy_streak(4),
            previous_commit=known_commit("sha-A"),
            previous_sent_status=sent_status("success", "stub-healthy"),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert outputs.new_commit == known_commit("sha-B")

        passed_state = stub_evaluator["aggregate_calls"][0]["state"]
        assert passed_state.consecutive_healthy == 0

        assert len(reporter.posts) == 1
        assert reporter.posts[0].sha == "sha-B"

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
            previous_state=healthy_streak(),
            previous_commit=known_commit("sha-A"),
            previous_sent_status=sent_status("success", "All healthy"),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert reporter.posts == []
        assert outputs.new_sent_status == sent_status("success", "All healthy")

    def test_null_reporter_is_called_and_dedup_state_is_tracked(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        base_inputs: CycleInputs,
    ) -> None:
        reporter = NullStatusReporter()

        outputs = run_cycle(base_inputs, reader, reporter, config, now=NOW)

        assert outputs.new_sent_status == sent_status("success", "stub-healthy")

    def test_missing_pr_sha_skips_post_but_still_writes_heartbeat(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
    ) -> None:
        reader.identity = ClusterIdentity(argocd_namespace="argocd", commit=no_commit())
        inputs = CycleInputs(
            previous_state=healthy_streak(),
            previous_commit=no_commit(),
            previous_sent_status=no_sent_status(),
        )

        outputs = run_cycle(inputs, reader, reporter, config, now=NOW)

        assert reporter.posts == []
        assert isinstance(outputs.new_commit, NoCommit)
        assert len(reader.heartbeat_writes) == 1

    def test_reporter_post_exception_propagates_loudly(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
    ) -> None:
        reporter.raise_on_post = RuntimeError("github 500")
        inputs = CycleInputs(
            previous_state=healthy_streak(),
            previous_commit=known_commit("sha-A"),
            previous_sent_status=sent_status("pending", "earlier"),
        )

        with pytest.raises(RuntimeError, match="github 500"):
            run_cycle(inputs, reader, reporter, config, now=NOW)

        assert reader.heartbeat_writes == []

    def test_heartbeat_failure_propagates_loudly(
        self,
        config: CycleConfig,
        reader: FakeClusterReader,
        reporter: RecordingReporter,
        base_inputs: CycleInputs,
    ) -> None:
        reader.raise_on_write_heartbeat = RuntimeError("k8s heartbeat write failed")

        with pytest.raises(RuntimeError, match="k8s heartbeat write failed"):
            run_cycle(base_inputs, reader, reporter, config, now=NOW)

        assert reader.heartbeat_writes == []
