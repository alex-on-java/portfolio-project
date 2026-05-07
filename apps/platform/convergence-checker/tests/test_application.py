from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from convergence_checker.application import ClusterIdentity, ConvergenceChecker, RuntimeSettings
from convergence_checker.domain import ApplicationSnapshot, PostedStatus, StageSnapshot


@dataclass(slots=True)
class FakeClock:
    current: datetime

    def __call__(self) -> datetime:
        return self.current


@dataclass(slots=True)
class FakeCluster:
    identity: ClusterIdentity = field(default_factory=lambda: ClusterIdentity("sha-a", "argocd"))
    applications: tuple[ApplicationSnapshot, ...] = field(default_factory=tuple)
    projects: tuple[str, ...] = field(default_factory=tuple)
    stages: tuple[StageSnapshot, ...] = field(default_factory=tuple)
    fail_identity: bool = False

    def read_cluster_identity(self) -> ClusterIdentity:
        if self.fail_identity:
            msg = "identity unavailable"
            raise RuntimeError(msg)
        return self.identity

    def list_applications(self, namespace: str) -> tuple[ApplicationSnapshot, ...]:
        assert namespace == self.identity.argocd_namespace
        return self.applications

    def list_projects(self) -> tuple[str, ...]:
        return self.projects

    def list_stages(self, namespaces: tuple[str, ...]) -> tuple[StageSnapshot, ...]:
        assert namespaces == self.projects
        return self.stages


@dataclass(slots=True)
class FakeHeartbeat:
    writes: list[datetime] = field(default_factory=list)
    fail: bool = False

    def write(self, observed_at: datetime) -> None:
        if self.fail:
            msg = "heartbeat unavailable"
            raise RuntimeError(msg)
        self.writes.append(observed_at)


@dataclass(slots=True)
class FakeReporter:
    posts: list[tuple[str, str, str]] = field(default_factory=list)
    fail: bool = False
    is_enabled: bool = True

    def enabled(self) -> bool:
        return self.is_enabled

    def post_status(self, *, sha: str, state: str, description: str) -> None:
        if self.fail:
            msg = "github unavailable"
            raise RuntimeError(msg)
        self.posts.append((sha, state, description))


def test_cycle_posts_status_and_writes_heartbeat() -> None:
    checker, reporter, heartbeat, _clock = _checker(
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
    )

    checker.evaluate_once()

    assert reporter.posts == [("sha-a", "pending", "1 resources pending")]
    assert heartbeat.writes == [datetime(2026, 5, 7, tzinfo=UTC)]


def test_missing_sha_skips_github_but_keeps_heartbeat() -> None:
    checker, reporter, heartbeat, _clock = _checker(
        identity=ClusterIdentity(None, "argocd"),
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
    )

    checker.evaluate_once()

    assert reporter.posts == []
    assert heartbeat.writes == [datetime(2026, 5, 7, tzinfo=UTC)]


def test_disabled_github_reporter_keeps_evaluating_and_heartbeating() -> None:
    checker, reporter, heartbeat, _clock = _checker(
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
        reporter=FakeReporter(is_enabled=False),
    )

    checker.evaluate_once()

    assert reporter.posts == []
    assert heartbeat.writes == [datetime(2026, 5, 7, tzinfo=UTC)]


def test_github_failure_does_not_update_post_memory_and_retries_next_cycle() -> None:
    reporter = FakeReporter(fail=True)
    checker, _reporter, heartbeat, clock = _checker(
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
        reporter=reporter,
    )

    checker.evaluate_once()
    clock.current += timedelta(seconds=12)
    reporter.fail = False
    checker.evaluate_once()

    assert checker.state.last_posted == PostedStatus("sha-a", "pending", "1 resources pending")
    assert reporter.posts == [("sha-a", "pending", "1 resources pending")]
    assert heartbeat.writes == [datetime(2026, 5, 7, tzinfo=UTC), datetime(2026, 5, 7, 0, 0, 12, tzinfo=UTC)]


def test_same_status_is_not_posted_twice_for_same_sha() -> None:
    checker, reporter, heartbeat, clock = _checker(
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
    )

    checker.evaluate_once()
    clock.current += timedelta(seconds=12)
    checker.evaluate_once()

    assert reporter.posts == [("sha-a", "pending", "1 resources pending")]
    assert len(heartbeat.writes) == 2


def test_sha_change_clears_dedup_and_posts_for_new_sha() -> None:
    cluster = FakeCluster(applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),))
    checker, reporter, _heartbeat, clock = _checker(cluster=cluster)

    checker.evaluate_once()
    cluster.identity = ClusterIdentity("sha-b", "argocd")
    clock.current += timedelta(seconds=12)
    checker.evaluate_once()

    assert reporter.posts == [
        ("sha-a", "pending", "1 resources pending"),
        ("sha-b", "pending", "1 resources pending"),
    ]


def test_cluster_read_failure_skips_evaluation_without_heartbeat() -> None:
    checker, reporter, heartbeat, _clock = _checker(cluster=FakeCluster(fail_identity=True))

    checker.evaluate_once()

    assert reporter.posts == []
    assert heartbeat.writes == []


def test_heartbeat_failure_does_not_rollback_successful_status_post() -> None:
    checker, reporter, heartbeat, _clock = _checker(
        applications=(ApplicationSnapshot("app-a", "Healthy", "OutOfSync", None),),
        heartbeat=FakeHeartbeat(fail=True),
    )

    checker.evaluate_once()

    assert reporter.posts == [("sha-a", "pending", "1 resources pending")]
    assert heartbeat.writes == []


def _checker(
    *,
    identity: ClusterIdentity | None = None,
    applications: tuple[ApplicationSnapshot, ...] = (),
    cluster: FakeCluster | None = None,
    heartbeat: FakeHeartbeat | None = None,
    reporter: FakeReporter | None = None,
) -> tuple[ConvergenceChecker, FakeReporter, FakeHeartbeat, FakeClock]:
    fake_cluster = cluster or FakeCluster(
        identity=identity or ClusterIdentity("sha-a", "argocd"),
        applications=applications,
    )
    fake_heartbeat = heartbeat or FakeHeartbeat()
    fake_reporter = reporter or FakeReporter()
    clock = FakeClock(datetime(2026, 5, 7, tzinfo=UTC))
    checker = ConvergenceChecker(
        settings=RuntimeSettings(check_interval_seconds=12, stability_threshold=5, safety_timeout_seconds=900),
        cluster_reader=fake_cluster,
        write_heartbeat=fake_heartbeat.write,
        status_reporter=fake_reporter,
        clock=clock,
    )
    return checker, fake_reporter, fake_heartbeat, clock
