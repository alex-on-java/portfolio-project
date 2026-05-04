from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from convergence_checker.io_adapters import CommitStatus, K8sClusterIdentityReader, K8sClusterReader, NullStatusReporter
from convergence_checker.k8s_repository import (
    K8sApplication,
    K8sProject,
    K8sRepository,
    K8sStage,
)

# ---------------------------------------------------------------------------
# K8sClusterIdentityReader
# ---------------------------------------------------------------------------


class TestK8sClusterIdentityReader:
    def test_delegates_to_repo_read_configmap(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.read_configmap.return_value = {"prCommitSha": "sha-abc"}
        reader = K8sClusterIdentityReader(
            repo=repo,
            namespace="shared-ns",
            configmap_name="identity-cm",
        )

        result = reader.read_cluster_identity()

        assert result == {"prCommitSha": "sha-abc"}
        repo.read_configmap.assert_called_once_with(name="identity-cm", namespace="shared-ns")


# ---------------------------------------------------------------------------
# K8sClusterReader translation
# ---------------------------------------------------------------------------


def _make_reader(repo: K8sRepository) -> K8sClusterReader:
    identity_reader = MagicMock()
    identity_reader.read_cluster_identity.return_value = {}
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
        assert apps[0].health_status == "Healthy"
        assert apps[0].sync_status == "Synced"
        assert apps[0].operation_phase == "Succeeded"
        repo.list_applications.assert_called_once_with("argocd")


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

        assert stages[0].conditions == {"Ready": True, "Healthy": True, "Verified": False}

    def test_unknown_condition_status_filtered_out(self) -> None:
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

        assert stages[0].conditions == {"Ready": True}
        assert "Healthy" not in stages[0].conditions

    def test_none_conditions_yields_empty_dict(self) -> None:
        repo = MagicMock(spec=K8sRepository)
        repo.list_stages.return_value = [
            K8sStage.model_validate(
                {"metadata": {"name": "stage-A", "namespace": "ns"}, "status": {"conditions": None}}
            )
        ]
        reader = _make_reader(repo)

        stages = reader.list_stages("ns")

        assert stages[0].conditions == {}

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
