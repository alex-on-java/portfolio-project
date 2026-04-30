from __future__ import annotations

import os
import signal
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from convergence_checker import cycle, github_client
from convergence_checker.config import settings
from convergence_checker.cycle import CycleConfig
from convergence_checker.io_adapters import (
    ClusterReader,
    GitHubStatusReporter,
    K8sClusterIdentityReader,
    K8sClusterReader,
    NullStatusReporter,
    StatusReporter,
)
from convergence_checker.models import ConvergenceState, CycleInputs

if TYPE_CHECKING:
    import types
    from collections.abc import Callable, Mapping

log: structlog.stdlib.BoundLogger = structlog.get_logger()

_DEFAULT_SA_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
_DEFAULT_OWN_NAMESPACE = "observability"
_DEFAULT_ARGOCD_NAMESPACE = "argocd"


def read_own_namespace(
    path: Path = _DEFAULT_SA_NAMESPACE_PATH,
    *,
    default: str = _DEFAULT_OWN_NAMESPACE,
) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return default


@dataclass
class ShutdownController:
    requested: bool = False

    def request_shutdown(self, _signum: int, _frame: types.FrameType | None) -> None:
        log.info("sigterm_received")
        self.requested = True

    def should_continue(self) -> bool:
        return not self.requested


def install_sigterm_handler(
    controller: ShutdownController,
    *,
    register: Callable[..., Any] = signal.signal,
) -> None:
    register(signal.SIGTERM, controller.request_shutdown)


def _load_k8s_clients() -> tuple[k8s_client.CoreV1Api, k8s_client.CustomObjectsApi]:
    k8s_config.load_incluster_config()
    return k8s_client.CoreV1Api(), k8s_client.CustomObjectsApi()


def select_reporter(*, dry_run: bool) -> StatusReporter:
    if dry_run:
        return NullStatusReporter()

    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

    if not app_id or not private_key or not installation_id:
        missing = [
            name
            for name, value in (
                ("GITHUB_APP_ID", app_id),
                ("GITHUB_APP_PRIVATE_KEY", private_key),
                ("GITHUB_APP_INSTALLATION_ID", installation_id),
            )
            if not value
        ]
        log.warning("github_credentials_missing", missing=missing)
        return NullStatusReporter()

    token_provider = github_client.GitHubAppTokenProvider(app_id, private_key, installation_id)
    return GitHubStatusReporter(github_client.GitHubAppClient(token_provider))


@dataclass(frozen=True)
class LoopPacing:
    sleep: Callable[[float], None]
    clock: Callable[[], datetime]
    should_continue: Callable[[], bool]
    interval_seconds: float


@dataclass(frozen=True)
class ClusterContext:
    argocd_namespace: str
    pr_commit_sha: str | None


def parse_cluster_identity(identity: Mapping[str, str]) -> ClusterContext:
    return ClusterContext(
        argocd_namespace=identity.get("argocdNamespace", _DEFAULT_ARGOCD_NAMESPACE),
        pr_commit_sha=identity.get("prCommitSha"),
    )


def build_initial_inputs(context: ClusterContext, *, dry_run: bool) -> CycleInputs:
    return CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit_sha=context.pr_commit_sha,
        previous_sent_status=None,
        dry_run=dry_run,
    )


def run_until(
    *,
    initial_inputs: CycleInputs,
    reader: ClusterReader,
    reporter: StatusReporter,
    config: CycleConfig,
    pacing: LoopPacing,
) -> None:
    inputs = initial_inputs
    while pacing.should_continue():
        try:
            outputs = cycle.run_cycle(inputs, reader, reporter, config, now=pacing.clock())
        except cycle.ABSORBED_FAULTS:
            log.exception("evaluation_cycle_failed")
        else:
            log.info(
                "evaluation",
                verdict=outputs.result.verdict.value,
                description=outputs.result.description,
                consecutive_healthy=outputs.new_state.consecutive_healthy,
                resources=outputs.resource_count,
            )
            inputs = CycleInputs(
                previous_state=outputs.new_state,
                previous_commit_sha=outputs.new_commit_sha,
                previous_sent_status=outputs.new_sent_status,
                dry_run=inputs.dry_run,
            )

        pacing.sleep(pacing.interval_seconds)


def boot_and_run(*, dry_run: bool = False) -> None:
    controller = ShutdownController()
    install_sigterm_handler(controller)
    core_api, custom_api = _load_k8s_clients()

    own_namespace = read_own_namespace()
    identity_reader = K8sClusterIdentityReader(
        core_api=core_api,
        namespace=settings.cluster_identity_namespace,
        configmap_name=settings.cluster_identity_configmap_name,
    )
    identity = identity_reader.read_cluster_identity()
    cluster_context = parse_cluster_identity(identity)

    if not cluster_context.pr_commit_sha:
        log.info("no_pr_context", msg="running in log-only mode")

    log.info(
        "checker_started",
        namespace=own_namespace,
        argocd_namespace=cluster_context.argocd_namespace,
        commit_sha=cluster_context.pr_commit_sha,
        dry_run=dry_run,
    )

    config = CycleConfig(
        stability_threshold=settings.stability_threshold,
        safety_timeout_seconds=settings.safety_timeout_seconds,
        owner_repo=settings.owner_repo,
        github_status_context=settings.github_status_context,
    )

    reader = K8sClusterReader(
        identity_reader=identity_reader,
        core_api=core_api,
        custom_api=custom_api,
        own_namespace=own_namespace,
        argocd_namespace=cluster_context.argocd_namespace,
        heartbeat_configmap_name=settings.heartbeat_configmap_name,
        field_manager_name=settings.field_manager_name,
    )
    initial_inputs = build_initial_inputs(cluster_context, dry_run=dry_run)
    pacing = LoopPacing(
        sleep=time.sleep,
        clock=lambda: datetime.now(tz=UTC),
        should_continue=controller.should_continue,
        interval_seconds=settings.check_interval_seconds,
    )

    run_until(
        initial_inputs=initial_inputs,
        reader=reader,
        reporter=select_reporter(dry_run=dry_run),
        config=config,
        pacing=pacing,
    )
