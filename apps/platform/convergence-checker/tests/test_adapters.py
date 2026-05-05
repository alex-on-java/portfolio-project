from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from convergence_checker.core.models import ClusterIdentity
from convergence_checker.core.ports import CommitStatus
from convergence_checker.infrastructure.github.adapters import NullStatusReporter
from convergence_checker.infrastructure.kubernetes.adapters import K8sClusterIdentityReader, K8sClusterReader
from convergence_checker.infrastructure.kubernetes.repository import (
    K8sApplication,
    K8sProject,
    K8sRepository,
    K8sStage,
)
from tests.factories import known_commit, no_operation_phase

# ---------------------------------------------------------------------------
# K8sClusterIdentityReader
# ---------------------------------------------------------------------------


class TestK8sClusterIdentityReader:
    def test_delegates_to_repo_read_configmap(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.read_configmap.return_value = {"argocdNamespace": "argocd", "prCommitSha": "sha-abc"}
        reader = K8sClusterIdentityReader(
            repo=repo,
            namespace="shared-ns",
            configmap_name="identity-cm",
        )

        result = reader.read_cluster_identity()

        assert result == ClusterIdentity(argocd_namespace="argocd", commit=known_commit("sha-abc"))
        repo.read_configmap.assert_called_once_with(name="identity-cm", namespace="shared-ns")

    def test_missing_required_argocd_namespace_fails_at_boundary(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.read_configmap.return_value = {"prCommitSha": "sha-abc"}
        reader = K8sClusterIdentityReader(
            repo=repo,
            namespace="shared-ns",
            configmap_name="identity-cm",
        )

        with pytest.raises(ValidationError):
            reader.read_cluster_identity()

    def test_blank_argocd_namespace_fails_at_boundary(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.read_configmap.return_value = {"argocdNamespace": " ", "prCommitSha": "sha-abc"}
        reader = K8sClusterIdentityReader(
            repo=repo,
            namespace="shared-ns",
            configmap_name="identity-cm",
        )

        with pytest.raises(ValidationError):
            reader.read_cluster_identity()

    def test_blank_pr_commit_sha_fails_at_boundary(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.read_configmap.return_value = {"argocdNamespace": "argocd", "prCommitSha": " "}
        reader = K8sClusterIdentityReader(
            repo=repo,
            namespace="shared-ns",
            configmap_name="identity-cm",
        )

        with pytest.raises(ValidationError):
            reader.read_cluster_identity()


# ---------------------------------------------------------------------------
# K8sClusterReader translation
# ---------------------------------------------------------------------------


def _make_reader(repo: K8sRepository) -> K8sClusterReader:
    identity_reader = MagicMock()
    identity_reader.read_cluster_identity.return_value = ClusterIdentity(
        argocd_namespace="argocd", commit=known_commit("sha")
    )
    return K8sClusterReader(
        identity_reader=identity_reader,
        repo=repo,
        own_namespace="own-ns",
        argocd_namespace="argocd",
        heartbeat_configmap_name="hb-cm",
        field_manager_name="test-fm",
    )


class TestK8sClusterReaderListApplications:
    def test_translates_dto_fields_to_domain_model(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_applications.return_value = [
            K8sApplication.model_validate(
                {
                    "metadata": {"name": "app-X"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "sync": {"status": "Synced"},
                        "operationState": {"phase": "Succeeded"},
                    },
                }
            )
        ]
        reader = _make_reader(repo)

        apps = reader.list_applications()

        assert len(apps) == 1
        assert apps[0].name == "app-X"
        assert apps[0].health_status.render() == "Healthy"
        assert apps[0].sync_status.render() == "Synced"
        assert apps[0].operation_phase.render() == "Succeeded"
        repo.list_applications.assert_called_once_with("argocd")

    def test_missing_operation_phase_maps_to_distinct_domain_state(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_applications.return_value = [
            K8sApplication.model_validate(
                {
                    "metadata": {"name": "app-X"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "sync": {"status": "Synced"},
                    },
                }
            )
        ]
        reader = _make_reader(repo)

        apps = reader.list_applications()

        assert apps[0].operation_phase == no_operation_phase()

    def test_empty_health_status_fails_at_dto_boundary(self) -> None:
        with pytest.raises(ValidationError):
            K8sApplication.model_validate(
                {
                    "metadata": {"name": "app-X"},
                    "status": {"health": {"status": ""}},
                }
            )


class TestK8sClusterReaderListStageNamespaces:
    def test_returns_project_names_as_namespaces(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_projects.return_value = [
            K8sProject.model_validate({"metadata": {"name": "proj-a"}}),
            K8sProject.model_validate({"metadata": {"name": "proj-b"}}),
        ]
        reader = _make_reader(repo)

        namespaces = reader.list_stage_namespaces()

        assert namespaces == ["proj-a", "proj-b"]


class TestK8sClusterReaderListStages:
    def test_true_and_false_conditions_translated(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_stages.return_value = [
            K8sStage.model_validate(
                {
                    "metadata": {"name": "stage-A", "namespace": "ns"},
                    "status": {
                        "health": {"status": "Healthy"},
                        "conditions": [
                            {"type": "Ready", "status": "True"},
                            {"type": "Healthy", "status": "True"},
                            {"type": "Verified", "status": "False"},
                        ],
                    },
                }
            )
        ]
        reader = _make_reader(repo)

        stages = reader.list_stages("ns")

        assert {name: condition.render() for name, condition in stages[0].conditions.items()} == {
            "Ready": "True",
            "Healthy": "True",
            "Verified": "False",
        }

    def test_unknown_condition_status_is_preserved(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_stages.return_value = [
            K8sStage.model_validate(
                {
                    "metadata": {"name": "stage-A", "namespace": "ns"},
                    "status": {
                        "conditions": [
                            {"type": "Ready", "status": "True"},
                            {"type": "Healthy", "status": "Unknown"},
                        ]
                    },
                }
            )
        ]
        reader = _make_reader(repo)

        stages = reader.list_stages("ns")

        assert {name: condition.render() for name, condition in stages[0].conditions.items()} == {
            "Ready": "True",
            "Healthy": "Unknown",
        }

    def test_none_conditions_yields_empty_dict(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_stages.return_value = [
            K8sStage.model_validate(
                {"metadata": {"name": "stage-A", "namespace": "ns"}, "status": {"conditions": None}}
            )
        ]
        reader = _make_reader(repo)

        stages = reader.list_stages("ns")

        assert dict(stages[0].conditions) == {}

    def test_write_heartbeat_delegates_to_repo(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        reader = _make_reader(repo)
        now = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)

        reader.write_heartbeat(now)

        repo.patch_configmap.assert_called_once_with(
            name="hb-cm",
            namespace="own-ns",
            data={"last-success": now.isoformat()},
            field_manager="test-fm",
        )


# ---------------------------------------------------------------------------
# NullStatusReporter
# ---------------------------------------------------------------------------


class TestNullStatusReporter:
    def test_post_accepts_any_status_and_returns_none(self) -> None:
        reporter = NullStatusReporter()
        status = CommitStatus(
            owner_repo="acme/repo",
            sha="sha-abc",
            state="pending",
            context="convergence",
            description="desc",
        )
        assert reporter.post(status) is None
