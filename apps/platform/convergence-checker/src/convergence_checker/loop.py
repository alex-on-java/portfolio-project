from __future__ import annotations

import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types
    from collections.abc import Callable

import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from convergence_checker import cycle, github_client
from convergence_checker.config import settings
from convergence_checker.cycle import CycleConfig, reconcile_startup_state
from convergence_checker.io_adapters import (
    GitHubStatusReporter,
    K8sClusterReader,
    NullStatusReporter,
    StatusReporter,
)
from convergence_checker.models import CycleInputs

log: structlog.stdlib.BoundLogger = structlog.get_logger()

_SA_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def _read_own_namespace() -> str:
    if _SA_NAMESPACE_PATH.exists():
        return _SA_NAMESPACE_PATH.read_text(encoding="utf-8").strip()
    return "observability"


def _install_sigterm_handler() -> Callable[[], bool]:
    shutdown = False

    def _handle_sigterm(_signum: int, _frame: types.FrameType | None) -> None:
        nonlocal shutdown
        log.info("sigterm_received")
        shutdown = True

    signal.signal(signal.SIGTERM, _handle_sigterm)

    def is_shutting_down() -> bool:
        return shutdown

    return is_shutting_down


def _load_k8s_clients() -> tuple[k8s_client.CoreV1Api, k8s_client.CustomObjectsApi]:
    k8s_config.load_incluster_config()
    return k8s_client.CoreV1Api(), k8s_client.CustomObjectsApi()


def _select_reporter(*, dry_run: bool) -> StatusReporter:
    if dry_run:
        return NullStatusReporter()

    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

    if not app_id or not private_key or not installation_id:
        log.warning("github_credentials_missing")
        return NullStatusReporter()

    return GitHubStatusReporter(github_client.GitHubAppClient(app_id, private_key, installation_id))


def run(*, dry_run: bool = False) -> None:
    shutdown = _install_sigterm_handler()
    core_api, custom_api = _load_k8s_clients()

    own_namespace = _read_own_namespace()
    reader = K8sClusterReader(
        core_api=core_api,
        custom_api=custom_api,
        own_namespace=own_namespace,
        cluster_identity_namespace=settings.cluster_identity_namespace,
        cluster_identity_configmap_name=settings.cluster_identity_configmap_name,
        state_configmap_name=settings.state_configmap_name,
        heartbeat_configmap_name=settings.heartbeat_configmap_name,
    )
    reporter = _select_reporter(dry_run=dry_run)

    identity = reader.read_cluster_identity()
    initial_sha = identity.get("prCommitSha")
    argocd_namespace = identity.get("argocdNamespace", "argocd")

    state = reconcile_startup_state(reader.read_state(), initial_sha)

    if not initial_sha:
        log.info("no_pr_context", msg="running in log-only mode")

    log.info(
        "checker_started",
        namespace=own_namespace,
        argocd_namespace=argocd_namespace,
        commit_sha=initial_sha,
        dry_run=dry_run,
    )

    reader_for_cycle = reader.with_argocd_namespace(argocd_namespace)
    config = CycleConfig(
        stability_threshold=settings.stability_threshold,
        safety_timeout_seconds=settings.safety_timeout_seconds,
        owner_repo=settings.owner_repo,
        github_status_context=settings.github_status_context,
    )
    inputs = CycleInputs(
        previous_state=state,
        previous_commit_sha=initial_sha,
        previous_sent_status=None,
        dry_run=dry_run,
    )

    while not shutdown():
        try:
            outputs = cycle.run_cycle(
                inputs,
                reader_for_cycle,
                reporter,
                config,
                now=datetime.now(tz=UTC),
            )
        except Exception:
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
                dry_run=dry_run,
            )

        time.sleep(settings.check_interval_seconds)
