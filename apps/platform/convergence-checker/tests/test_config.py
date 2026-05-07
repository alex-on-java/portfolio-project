from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from convergence_checker.infrastructure.config import load_settings

if TYPE_CHECKING:
    from pathlib import Path


def test_load_settings_combines_toml_prefixed_env_and_github_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        "check_interval_seconds = 3\nstability_threshold = 2\nsafety_timeout_seconds = 30\n",
        encoding="utf-8",
    )
    namespace_path = tmp_path / "namespace"
    namespace_path.write_text("observability\n", encoding="utf-8")
    monkeypatch.setenv("CONVERGENCE_CHECKER_OWNER_REPO", "example/project")
    monkeypatch.setenv("CONVERGENCE_CHECKER_CLUSTER_IDENTITY_NAMESPACE", "identity-ns")
    monkeypatch.setenv("CONVERGENCE_CHECKER_CLUSTER_IDENTITY_CONFIGMAP_NAME", "identity-cm")
    monkeypatch.setenv("CONVERGENCE_CHECKER_HEARTBEAT_CONFIGMAP_NAME", "heartbeat-cm")
    monkeypatch.setenv("CONVERGENCE_CHECKER_FIELD_MANAGER_NAME", "field-owner")
    monkeypatch.setenv("GITHUB_APP_ID", "123")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", "private-key")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "456")

    settings = load_settings(settings_path=settings_path, namespace_path=namespace_path)

    assert settings.runtime.check_interval_seconds == 3
    assert settings.runtime.stability_threshold == 2
    assert settings.runtime.safety_timeout_seconds == 30
    assert settings.kubernetes.cluster_identity_namespace == "identity-ns"
    assert settings.kubernetes.cluster_identity_configmap_name == "identity-cm"
    assert settings.kubernetes.heartbeat_namespace == "observability"
    assert settings.kubernetes.heartbeat_configmap_name == "heartbeat-cm"
    assert settings.kubernetes.field_manager_name == "field-owner"
    assert settings.github.owner_repo == "example/project"
    assert settings.github.posting_enabled


def test_missing_external_resource_name_fails_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        "check_interval_seconds = 3\nstability_threshold = 2\nsafety_timeout_seconds = 30\n",
        encoding="utf-8",
    )
    namespace_path = tmp_path / "namespace"
    namespace_path.write_text("observability\n", encoding="utf-8")
    monkeypatch.setenv("CONVERGENCE_CHECKER_OWNER_REPO", "example/project")

    with pytest.raises(ValueError, match="cluster_identity_namespace"):
        load_settings(settings_path=settings_path, namespace_path=namespace_path)


def test_absent_github_credentials_disable_posting_without_startup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_path = tmp_path / "settings.toml"
    settings_path.write_text(
        "check_interval_seconds = 3\nstability_threshold = 2\nsafety_timeout_seconds = 30\n",
        encoding="utf-8",
    )
    namespace_path = tmp_path / "namespace"
    namespace_path.write_text("observability\n", encoding="utf-8")
    monkeypatch.setenv("CONVERGENCE_CHECKER_OWNER_REPO", "example/project")
    monkeypatch.setenv("CONVERGENCE_CHECKER_CLUSTER_IDENTITY_NAMESPACE", "identity-ns")
    monkeypatch.setenv("CONVERGENCE_CHECKER_CLUSTER_IDENTITY_CONFIGMAP_NAME", "identity-cm")
    monkeypatch.setenv("CONVERGENCE_CHECKER_HEARTBEAT_CONFIGMAP_NAME", "heartbeat-cm")
    monkeypatch.setenv("CONVERGENCE_CHECKER_FIELD_MANAGER_NAME", "field-owner")

    settings = load_settings(settings_path=settings_path, namespace_path=namespace_path)

    assert not settings.github.posting_enabled
