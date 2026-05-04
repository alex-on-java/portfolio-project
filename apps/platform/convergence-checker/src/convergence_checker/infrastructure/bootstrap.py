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

from convergence_checker.core.cycle import CycleConfig
from convergence_checker.core.models import ConvergenceState, CycleInputs
from convergence_checker.infrastructure.config import settings
from convergence_checker.infrastructure.github.adapters import (
    GitHubStatusReporter,
    NullStatusReporter,
)
from convergence_checker.infrastructure.github.repository import (
    GitHubAppTokenProvider,
    GitHubRepository,
)
from convergence_checker.infrastructure.kubernetes.adapters import (
    K8sClusterIdentityReader,
    K8sClusterReader,
)
from convergence_checker.infrastructure.kubernetes.repository import K8sRepository
from convergence_checker.infrastructure.runner import LoopPacing, run_until

if TYPE_CHECKING:
    import types
    from collections.abc import Callable, Mapping

    from convergence_checker.core.ports import StatusReporter

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


def _build_repository() -> K8sRepository:
    k8s_config.load_incluster_config()
    return K8sRepository(
        core_api=k8s_client.CoreV1Api(),
        custom_api=k8s_client.CustomObjectsApi(),
    )


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

    token_provider = GitHubAppTokenProvider(app_id, private_key, installation_id)
    return GitHubStatusReporter(GitHubRepository(token_provider))


@dataclass(frozen=True)
class ClusterContext:
    argocd_namespace: str
    pr_commit_sha: str | None


def parse_cluster_identity(identity: Mapping[str, str]) -> ClusterContext:
    return ClusterContext(
        argocd_namespace=identity.get("argocdNamespace", _DEFAULT_ARGOCD_NAMESPACE),
        pr_commit_sha=identity.get("prCommitSha"),
    )


def build_initial_inputs(context: ClusterContext) -> CycleInputs:
    return CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit_sha=context.pr_commit_sha,
        previous_sent_status=None,
    )


def boot_and_run(*, dry_run: bool = False) -> None:
    controller = ShutdownController()
    install_sigterm_handler(controller)
    repo = _build_repository()

    own_namespace = read_own_namespace()
    identity_reader = K8sClusterIdentityReader(
        repo=repo,
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
        repo=repo,
        own_namespace=own_namespace,
        argocd_namespace=cluster_context.argocd_namespace,
        heartbeat_configmap_name=settings.heartbeat_configmap_name,
        field_manager_name=settings.field_manager_name,
    )
    initial_inputs = build_initial_inputs(cluster_context)
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
