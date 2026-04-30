from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import responses
from anyio.from_thread import start_blocking_portal
from kmock import KubernetesEmulator, Server
from kubernetes import client as k8s_client

from convergence_checker import cycle
from convergence_checker.cycle import CycleConfig
from convergence_checker.github_client import GitHubAppClient
from convergence_checker.io_adapters import (
    GitHubStatusReporter,
    K8sClusterIdentityReader,
    K8sClusterReader,
    StaticTokenProvider,
)
from convergence_checker.models import (
    ConvergenceState,
    CycleInputs,
    EvaluationVerdict,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def served_kmock() -> Iterator[KubernetesEmulator]:
    with ExitStack() as stack:
        portal = stack.enter_context(start_blocking_portal(backend="asyncio"))
        kmock = portal.call(KubernetesEmulator)
        stack.enter_context(portal.wrap_async_context_manager(kmock))
        stack.enter_context(portal.wrap_async_context_manager(Server(kmock)))
        yield kmock


def _seed(kmock: KubernetesEmulator) -> None:
    kmock.resources["argoproj.io/v1alpha1/applications"] = {
        "kind": "Application",
        "singular": "application",
        "namespaced": True,
        "verbs": {"get", "list", "watch"},
    }
    kmock.resources["kargo.akuity.io/v1alpha1/projects"] = {
        "kind": "Project",
        "singular": "project",
        "namespaced": False,
        "verbs": {"get", "list", "watch"},
    }
    kmock.resources["kargo.akuity.io/v1alpha1/stages"] = {
        "kind": "Stage",
        "singular": "stage",
        "namespaced": True,
        "verbs": {"get", "list", "watch"},
    }

    kmock.objects["v1/configmaps", "test-shared-ns", "test-identity-cm"] = {
        "metadata": {"name": "test-identity-cm", "namespace": "test-shared-ns"},
        "data": {"prCommitSha": "sha-test", "argocdNamespace": "test-argocd-ns"},
    }
    kmock.objects["v1/configmaps", "test-own-ns", "test-heartbeat-cm"] = {
        "metadata": {"name": "test-heartbeat-cm", "namespace": "test-own-ns"},
        "data": {},
    }

    kmock.objects["argoproj.io/v1alpha1/applications", "test-argocd-ns", "app-A"] = {
        "metadata": {"name": "app-A", "namespace": "test-argocd-ns"},
        "status": {
            "health": {"status": "Healthy"},
            "sync": {"status": "Synced"},
            "operationState": {"phase": "Succeeded"},
        },
    }
    kmock.objects["argoproj.io/v1alpha1/applications", "test-argocd-ns", "app-B"] = {
        "metadata": {"name": "app-B", "namespace": "test-argocd-ns"},
        "status": {
            "health": {"status": "Degraded"},
            "sync": {"status": "Synced"},
        },
    }

    kmock.objects["kargo.akuity.io/v1alpha1/projects", None, "test-kargo-project"] = {
        "metadata": {"name": "test-kargo-project"},
    }

    kmock.objects["kargo.akuity.io/v1alpha1/stages", "test-kargo-project", "stage-X"] = {
        "metadata": {"name": "stage-X", "namespace": "test-kargo-project"},
        "status": {
            "health": {"status": "Healthy"},
            "conditions": [
                {"type": "Ready", "status": "True"},
                {"type": "Healthy", "status": "True"},
                {"type": "Verified", "status": "True"},
            ],
        },
    }
    kmock.objects["kargo.akuity.io/v1alpha1/stages", "test-kargo-project", "stage-Y"] = {
        "metadata": {"name": "stage-Y", "namespace": "test-kargo-project"},
        "status": {"health": {"status": "Unhealthy"}},
    }


def _build_reader(host: str) -> K8sClusterReader:
    cfg = k8s_client.Configuration()
    cfg.host = host
    cfg.verify_ssl = False
    api = k8s_client.ApiClient(cfg)
    core = k8s_client.CoreV1Api(api)
    identity_reader = K8sClusterIdentityReader(
        core_api=core,
        namespace="test-shared-ns",
        configmap_name="test-identity-cm",
    )
    return K8sClusterReader(
        identity_reader=identity_reader,
        core_api=core,
        custom_api=k8s_client.CustomObjectsApi(api),
        own_namespace="test-own-ns",
        argocd_namespace="test-argocd-ns",
        heartbeat_configmap_name="test-heartbeat-cm",
        field_manager_name="test-manager",
    )


def test_run_cycle_failure_verdict(served_kmock: KubernetesEmulator) -> None:
    _seed(served_kmock)

    reader = _build_reader(str(served_kmock.url).rstrip("/"))
    reporter = GitHubStatusReporter(GitHubAppClient(StaticTokenProvider("ghs_test")))
    config = CycleConfig(
        stability_threshold=3,
        safety_timeout_seconds=600,
        owner_repo="acme/repo",
        github_status_context="convergence",
    )
    inputs = CycleInputs(
        previous_state=ConvergenceState(),
        previous_commit_sha="sha-test",
        previous_sent_status=None,
    )

    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.github.com/repos/acme/repo/statuses/sha-test",
            json={},
            status=201,
        )
        outputs = cycle.run_cycle(
            inputs,
            reader,
            reporter,
            config,
            now=datetime.now(tz=UTC),
        )

    assert outputs.result.verdict == EvaluationVerdict.FAILURE
    assert "Degraded" in outputs.result.description
    assert "Unhealthy" in outputs.result.description
    assert outputs.resource_count == 4
