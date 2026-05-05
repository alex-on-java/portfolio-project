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
from convergence_checker.core.models import (
    ClusterIdentity,
    ConvergenceState,
    CycleInputs,
    KnownCommit,
    NoCommit,
    NoSentStatus,
)
from convergence_checker.infrastructure.config import RuntimeSettings, load_settings
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
    from collections.abc import Callable

    from convergence_checker.core.ports import StatusReporter

log: structlog.stdlib.BoundLogger = structlog.get_logger()

_DEFAULT_SA_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def read_own_namespace(
    path: Path = _DEFAULT_SA_NAMESPACE_PATH,
    *,
    default: str | None = None,
) -> str:
    if path.exists():
        namespace = path.read_text(encoding="utf-8").strip()
        if namespace:
            return namespace
        msg = f"Service-account namespace file is empty: {path}"
        raise RuntimeError(msg)
    if default is not None:
        return default
    msg = f"Service-account namespace file is required: {path}"
    raise RuntimeError(msg)


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
        joined = ", ".join(missing)
        msg = f"GitHub App credentials are required outside dry-run; missing: {joined}"
        raise RuntimeError(msg)

    token_provider = GitHubAppTokenProvider(app_id, private_key, installation_id)
    return GitHubStatusReporter(GitHubRepository(token_provider))


@dataclass(frozen=True)
class ClusterContext:
    argocd_namespace: str
    identity: ClusterIdentity


def build_cluster_context(identity: ClusterIdentity) -> ClusterContext:
    return ClusterContext(
        argocd_namespace=identity.argocd_namespace,
        identity=identity,
    )


def build_initial_inputs(context: ClusterContext) -> CycleInputs:
    return CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit=context.identity.commit,
        previous_sent_status=NoSentStatus(),
    )


def boot_and_run(*, dry_run: bool = False) -> None:
    runtime_settings = load_settings()
    controller = ShutdownController()
    install_sigterm_handler(controller)
    repo = _build_repository()

    own_namespace = read_own_namespace()
    identity_reader = K8sClusterIdentityReader(
        repo=repo,
        namespace=runtime_settings.cluster.cluster_identity_namespace,
        configmap_name=runtime_settings.cluster.cluster_identity_configmap_name,
    )
    identity = identity_reader.read_cluster_identity()
    cluster_context = build_cluster_context(identity)

    if isinstance(cluster_context.identity.commit, NoCommit):
        log.info("no_pr_context", msg="running in log-only mode")

    commit_sha = (
        cluster_context.identity.commit.sha if isinstance(cluster_context.identity.commit, KnownCommit) else None
    )
    log.info(
        "checker_started",
        namespace=own_namespace,
        argocd_namespace=cluster_context.argocd_namespace,
        commit_sha=commit_sha,
        dry_run=dry_run,
    )

    config = _cycle_config(runtime_settings)

    reader = K8sClusterReader(
        identity_reader=identity_reader,
        repo=repo,
        own_namespace=own_namespace,
        argocd_namespace=cluster_context.argocd_namespace,
        heartbeat_configmap_name=runtime_settings.cluster.heartbeat_configmap_name,
        field_manager_name=runtime_settings.cluster.field_manager_name,
    )
    initial_inputs = build_initial_inputs(cluster_context)
    pacing = LoopPacing(
        sleep=time.sleep,
        clock=lambda: datetime.now(tz=UTC),
        should_continue=controller.should_continue,
        interval_seconds=runtime_settings.loop.check_interval_seconds,
    )

    run_until(
        initial_inputs=initial_inputs,
        reader=reader,
        reporter=select_reporter(dry_run=dry_run),
        config=config,
        pacing=pacing,
    )


def _cycle_config(settings: RuntimeSettings) -> CycleConfig:
    return CycleConfig(
        stability_threshold=settings.loop.stability_threshold,
        safety_timeout_seconds=settings.loop.safety_timeout_seconds,
        owner_repo=settings.github.owner_repo,
        github_status_context=settings.github.github_status_context,
    )
