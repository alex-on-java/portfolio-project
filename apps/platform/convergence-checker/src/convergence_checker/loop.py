from __future__ import annotations

import os
import signal
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types

import structlog
from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from convergence_checker import evaluator, github_client
from convergence_checker import k8s_client as k8s
from convergence_checker.config import settings
from convergence_checker.models import (
    ApplicationStatus,
    ConvergenceState,
    EvaluationResult,
    EvaluationVerdict,
    StageStatus,
)

log: structlog.stdlib.BoundLogger = structlog.get_logger()

_SA_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def _read_own_namespace() -> str:
    if _SA_NAMESPACE_PATH.exists():
        return _SA_NAMESPACE_PATH.read_text().strip()
    return "observability"


def _read_cluster_identity(
    core_api: k8s_client.CoreV1Api,
) -> dict[str, str]:
    return k8s.read_configmap(
        core_api,
        name=settings.cluster_identity_configmap_name,
        namespace=settings.cluster_identity_namespace,
    )


def _build_github_client() -> github_client.GitHubAppClient | None:
    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

    if not app_id or not private_key or not installation_id:
        log.warning("github_credentials_missing")
        return None

    return github_client.GitHubAppClient(app_id, private_key, installation_id)


def _collect_evaluations(
    custom_api: k8s_client.CustomObjectsApi,
    argocd_namespace: str,
    kargo_namespaces: list[str],
) -> list[EvaluationResult]:
    results: list[EvaluationResult] = []

    apps = k8s.list_applications(custom_api, argocd_namespace)
    for raw_app in apps:
        app = ApplicationStatus.from_resource(raw_app)
        if evaluator.is_self_application(app.name):
            continue
        results.append(evaluator.evaluate_app(app))

    for ns in kargo_namespaces:
        stages = k8s.list_stages(custom_api, ns)
        for raw_stage in stages:
            stage = StageStatus.from_resource(raw_stage)
            results.append(evaluator.evaluate_stage(stage))

    return results


def _write_heartbeat(core_api: k8s_client.CoreV1Api, namespace: str) -> None:
    now = datetime.now(tz=UTC).isoformat()
    k8s.patch_configmap(
        core_api,
        name=settings.heartbeat_configmap_name,
        namespace=namespace,
        data={"last-success": now},
    )


def _write_state(core_api: k8s_client.CoreV1Api, namespace: str, state: ConvergenceState) -> None:
    k8s.patch_configmap(
        core_api,
        name=settings.state_configmap_name,
        namespace=namespace,
        data={"state": state.model_dump_json()},
    )


def _load_state(core_api: k8s_client.CoreV1Api, namespace: str) -> ConvergenceState:
    try:
        data = k8s.read_configmap(core_api, name=settings.state_configmap_name, namespace=namespace)
        raw = data.get("state")
        if raw:
            return ConvergenceState.model_validate_json(raw)
    except (KeyError, ValueError, k8s_client.ApiException):
        log.debug("state_configmap_not_found_or_invalid")
    return ConvergenceState()


def _github_state_from_verdict(verdict: EvaluationVerdict) -> str:
    mapping: dict[EvaluationVerdict, str] = {
        EvaluationVerdict.HEALTHY: "success",
        EvaluationVerdict.PENDING: "pending",
        EvaluationVerdict.FAILURE: "failure",
    }
    return mapping[verdict]


def _discover_kargo_namespaces(custom_api: k8s_client.CustomObjectsApi) -> list[str]:
    projects = k8s.list_projects(custom_api)
    namespaces: list[str] = []
    for project in projects:
        metadata = project.get("metadata", {})
        if isinstance(metadata, dict):
            name = metadata.get("name")
            if isinstance(name, str):
                namespaces.append(name)
    return namespaces


def run(*, dry_run: bool = False) -> None:
    shutdown = False

    def _handle_sigterm(_signum: int, _frame: types.FrameType | None) -> None:
        nonlocal shutdown
        log.info("sigterm_received")
        shutdown = True

    signal.signal(signal.SIGTERM, _handle_sigterm)

    k8s_config.load_incluster_config()
    core_api = k8s_client.CoreV1Api()
    custom_api = k8s_client.CustomObjectsApi()

    own_namespace = _read_own_namespace()
    gh_client = _build_github_client()
    owner_repo: str = settings.owner_repo
    status_context: str = settings.github_status_context

    identity = _read_cluster_identity(core_api)
    commit_sha = identity.get("prCommitSha")
    argocd_namespace = identity.get("argocdNamespace", "argocd")

    state = _load_state(core_api, own_namespace)
    state = ConvergenceState(
        consecutive_healthy=state.consecutive_healthy,
        first_pending_at=state.first_pending_at,
        last_commit_sha=commit_sha,
    )

    if not commit_sha:
        log.info("no_pr_context", msg="running in log-only mode")

    log.info(
        "checker_started",
        namespace=own_namespace,
        argocd_namespace=argocd_namespace,
        commit_sha=commit_sha,
        dry_run=dry_run,
    )

    while not shutdown:
        identity = _read_cluster_identity(core_api)
        new_sha = identity.get("prCommitSha")

        if new_sha and new_sha != state.last_commit_sha:
            log.info("sha_changed", old=state.last_commit_sha, new=new_sha)
            state = ConvergenceState(last_commit_sha=new_sha)
            commit_sha = new_sha

        kargo_namespaces = _discover_kargo_namespaces(custom_api)

        results = _collect_evaluations(custom_api, argocd_namespace, kargo_namespaces)

        result, state = evaluator.aggregate(
            results,
            state,
            stability_threshold=settings.stability_threshold,
            safety_timeout_seconds=settings.safety_timeout_seconds,
        )

        log.info(
            "evaluation",
            verdict=result.verdict.value,
            description=result.description,
            consecutive_healthy=state.consecutive_healthy,
            resources=len(results),
        )

        if commit_sha and gh_client and not dry_run:
            gh_state = _github_state_from_verdict(result.verdict)
            try:
                gh_client.create_commit_status(
                    owner_repo=owner_repo,
                    sha=commit_sha,
                    state=gh_state,
                    context=status_context,
                    description=result.description,
                )
                log.info("github_status_reported", state=gh_state)
            except Exception:
                log.exception("github_status_failed")

        try:
            _write_heartbeat(core_api, own_namespace)
        except Exception:
            log.exception("heartbeat_write_failed")

        try:
            _write_state(core_api, own_namespace, state)
        except Exception:
            log.exception("state_write_failed")

        time.sleep(settings.check_interval_seconds)
