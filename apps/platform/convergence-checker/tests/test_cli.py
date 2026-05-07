from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING

from click.testing import CliRunner

from convergence_checker.application import RuntimeSettings
from convergence_checker.infrastructure import cli as cli_module
from convergence_checker.infrastructure.config import AppSettings, GithubAppSettings, KubernetesSettings

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


@dataclass(slots=True)
class CreatedChecker:
    ran: bool = False

    def run_forever(self) -> None:
        self.ran = True


def test_cli_wires_runtime_components(monkeypatch: pytest.MonkeyPatch) -> None:
    created_checker = CreatedChecker()
    app_settings = AppSettings(
        runtime=RuntimeSettings(check_interval_seconds=12, stability_threshold=5, safety_timeout_seconds=900),
        kubernetes=KubernetesSettings(
            cluster_identity_namespace="identity-ns",
            cluster_identity_configmap_name="identity-cm",
            heartbeat_namespace="observability",
            heartbeat_configmap_name="heartbeat-cm",
            field_manager_name="field-owner",
        ),
        github=GithubAppSettings(
            owner_repo="example/project",
            app_id=None,
            private_key=None,
            installation_id=None,
        ),
    )

    def load_fake_settings(*, settings_path: Path) -> AppSettings:
        _ = settings_path
        return app_settings

    def fake_cluster_factory(settings: KubernetesSettings) -> object:
        _ = settings
        return SimpleNamespace(write=lambda _observed_at: None)

    def fake_reporter_factory(settings: GithubAppSettings) -> object:
        _ = settings
        return object()

    monkeypatch.setattr(cli_module, "load_settings", load_fake_settings)
    monkeypatch.setattr(cli_module.KubernetesGateway, "in_cluster", fake_cluster_factory)
    monkeypatch.setattr(cli_module.GithubStatusReporter, "from_settings", fake_reporter_factory)

    def checker_factory(**_kwargs: object) -> CreatedChecker:
        return created_checker

    monkeypatch.setattr(cli_module, "ConvergenceChecker", checker_factory)

    result = CliRunner().invoke(cli_module.cli, ["--settings", "pyproject.toml"])

    assert result.exit_code == 0
    assert created_checker.ran
