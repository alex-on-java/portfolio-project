from __future__ import annotations

import signal
from typing import TYPE_CHECKING

import pytest
from dynaconf import Dynaconf
from dynaconf.validator import ValidationError

from convergence_checker.core.models import ClusterIdentity
from convergence_checker.infrastructure.bootstrap import (
    ClusterContext,
    ShutdownController,
    build_cluster_context,
    build_initial_inputs,
    install_sigterm_handler,
    read_own_namespace,
    select_reporter,
)
from convergence_checker.infrastructure.config import load_settings
from convergence_checker.infrastructure.github.adapters import (
    GitHubStatusReporter,
    NullStatusReporter,
)
from tests.factories import healthy_streak, known_commit, no_commit, no_sent_status

if TYPE_CHECKING:
    import types
    from collections.abc import Callable
    from pathlib import Path


# ---------------------------------------------------------------------------
# read_own_namespace
# ---------------------------------------------------------------------------


class TestReadOwnNamespace:
    def test_reads_stripped_contents_when_path_exists(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "namespace"
        ns_file.write_text("kargo-shared-resources\n")
        assert read_own_namespace(ns_file) == "kargo-shared-resources"

    def test_raises_when_path_missing_without_explicit_default(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "missing"
        with pytest.raises(RuntimeError, match="required"):
            read_own_namespace(ns_file)

    def test_returns_explicit_default(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "missing"
        assert read_own_namespace(ns_file, default="custom-default") == "custom-default"

    def test_empty_namespace_file_fails_loudly(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "namespace"
        ns_file.write_text("\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="empty"):
            read_own_namespace(ns_file)


# ---------------------------------------------------------------------------
# ShutdownController + install_sigterm_handler
# ---------------------------------------------------------------------------


class TestShutdownController:
    def test_initially_should_continue(self) -> None:
        controller = ShutdownController()
        assert controller.should_continue() is True
        assert controller.requested is False

    def test_request_shutdown_flips_state(self) -> None:
        controller = ShutdownController()
        controller.request_shutdown(signal.SIGTERM, None)
        assert controller.requested is True
        assert controller.should_continue() is False


class TestInstallSigtermHandler:
    def test_register_called_with_sigterm_and_handler_that_flips_controller(self) -> None:
        controller = ShutdownController()
        captured: dict[str, object] = {}

        def fake_register(signum: int, handler: Callable[[int, types.FrameType | None], None]) -> None:
            captured["signum"] = signum
            captured["handler"] = handler

        install_sigterm_handler(controller, register=fake_register)

        assert captured["signum"] == signal.SIGTERM
        captured_handler = captured["handler"]
        assert callable(captured_handler)
        captured_handler(signal.SIGTERM, None)
        assert controller.requested is True

    def test_default_register_installs_handler_into_signal_module(self) -> None:
        controller = ShutdownController()
        prev = signal.getsignal(signal.SIGTERM)
        try:
            install_sigterm_handler(controller)
            installed = signal.getsignal(signal.SIGTERM)
            assert callable(installed)
            installed(signal.SIGTERM, None)
            assert controller.requested is True
        finally:
            signal.signal(signal.SIGTERM, prev)


# ---------------------------------------------------------------------------
# select_reporter
# ---------------------------------------------------------------------------


_GH_ENV_VARS = ("GITHUB_APP_ID", "GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_INSTALLATION_ID")
_VALID_PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nFAKE\n-----END RSA PRIVATE KEY-----\n"


@pytest.fixture
def clean_gh_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _GH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.mark.usefixtures("clean_gh_env")
class TestSelectReporter:
    def test_dry_run_returns_null_reporter(self) -> None:
        assert isinstance(select_reporter(dry_run=True), NullStatusReporter)

    def test_dry_run_short_circuits_even_when_credentials_present(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "123")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _VALID_PRIVATE_KEY)
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "456")

        assert isinstance(select_reporter(dry_run=True), NullStatusReporter)

    def test_missing_credentials_fail_loudly(self) -> None:
        with pytest.raises(RuntimeError, match="GITHUB_APP_ID"):
            select_reporter(dry_run=False)

    def test_partial_credentials_fail_loudly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "123")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _VALID_PRIVATE_KEY)
        with pytest.raises(RuntimeError, match="GITHUB_APP_INSTALLATION_ID"):
            select_reporter(dry_run=False)

    def test_complete_credentials_build_github_reporter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "123")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _VALID_PRIVATE_KEY)
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "456")

        assert isinstance(select_reporter(dry_run=False), GitHubStatusReporter)


# ---------------------------------------------------------------------------
# cluster identity parsing
# ---------------------------------------------------------------------------


class TestBuildClusterContext:
    def test_argocd_namespace_from_identity(self) -> None:
        context = build_cluster_context(ClusterIdentity(argocd_namespace="argo-prod", commit=known_commit("sha-1")))
        assert context.argocd_namespace == "argo-prod"

    def test_pr_commit_sha_from_identity(self) -> None:
        context = build_cluster_context(ClusterIdentity(argocd_namespace="argocd", commit=known_commit("sha-abc")))
        assert context.identity.commit == known_commit("sha-abc")

    def test_missing_pr_commit_sha_yields_no_commit_state(self) -> None:
        context = build_cluster_context(ClusterIdentity(argocd_namespace="argocd", commit=no_commit()))
        assert context.identity.commit == no_commit()


class TestBuildInitialInputs:
    def test_initial_inputs_seeded_from_context_sha(self) -> None:
        inputs = build_initial_inputs(
            ClusterContext(
                argocd_namespace="argocd",
                identity=ClusterIdentity(argocd_namespace="argocd", commit=known_commit("sha-abc")),
            )
        )
        assert inputs.previous_commit == known_commit("sha-abc")
        assert inputs.previous_state == healthy_streak()
        assert inputs.previous_sent_status == no_sent_status()

    def test_no_commit_state_is_preserved(self) -> None:
        inputs = build_initial_inputs(
            ClusterContext(
                argocd_namespace="argocd",
                identity=ClusterIdentity(argocd_namespace="argocd", commit=no_commit()),
            )
        )
        assert inputs.previous_commit == no_commit()


class TestLoadSettings:
    def test_valid_settings_are_loaded_as_typed_values(self) -> None:
        settings = Dynaconf(
            settings_files=[],
            cluster_identity_namespace="identity-ns",
            cluster_identity_configmap_name="identity-cm",
            heartbeat_configmap_name="heartbeat-cm",
            field_manager_name="convergence-checker",
            owner_repo="acme/repo",
            github_status_context="convergence",
            check_interval_seconds=12,
            stability_threshold=5,
            safety_timeout_seconds=900,
        )

        loaded = load_settings(settings)

        assert loaded.github.owner_repo == "acme/repo"
        assert loaded.loop.stability_threshold == 5

    def test_missing_required_setting_fails_loudly(self) -> None:
        settings = Dynaconf(
            settings_files=[],
            cluster_identity_namespace="identity-ns",
            cluster_identity_configmap_name="identity-cm",
            heartbeat_configmap_name="heartbeat-cm",
            field_manager_name="convergence-checker",
            github_status_context="convergence",
            check_interval_seconds=12,
            stability_threshold=5,
            safety_timeout_seconds=900,
        )

        with pytest.raises(ValidationError, match="owner_repo"):
            load_settings(settings)
