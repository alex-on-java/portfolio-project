from __future__ import annotations

import signal
from typing import TYPE_CHECKING

import pytest

from convergence_checker.io_adapters import (
    GitHubStatusReporter,
    NullStatusReporter,
)
from convergence_checker.loop import (
    ClusterContext,
    ShutdownController,
    build_initial_inputs,
    install_sigterm_handler,
    parse_cluster_identity,
    read_own_namespace,
    select_reporter,
)
from convergence_checker.models import ConvergenceState

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

    def test_returns_default_when_path_missing(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "missing"
        assert read_own_namespace(ns_file) == "observability"

    def test_returns_explicit_default(self, tmp_path: Path) -> None:
        ns_file = tmp_path / "missing"
        assert read_own_namespace(ns_file, default="custom-default") == "custom-default"


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

    def test_missing_credentials_falls_back_to_null(self) -> None:
        assert isinstance(select_reporter(dry_run=False), NullStatusReporter)

    def test_partial_credentials_falls_back_to_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "123")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _VALID_PRIVATE_KEY)
        assert isinstance(select_reporter(dry_run=False), NullStatusReporter)

    def test_complete_credentials_build_github_reporter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_APP_ID", "123")
        monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", _VALID_PRIVATE_KEY)
        monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "456")

        assert isinstance(select_reporter(dry_run=False), GitHubStatusReporter)


# ---------------------------------------------------------------------------
# cluster identity parsing
# ---------------------------------------------------------------------------


class TestParseClusterIdentity:
    def test_argocd_namespace_from_identity(self) -> None:
        context = parse_cluster_identity({"argocdNamespace": "argo-prod", "prCommitSha": "sha-1"})
        assert context.argocd_namespace == "argo-prod"

    def test_missing_argocd_namespace_defaults_to_argocd(self) -> None:
        context = parse_cluster_identity({"prCommitSha": "sha-1"})
        assert context.argocd_namespace == "argocd"

    def test_pr_commit_sha_from_identity(self) -> None:
        context = parse_cluster_identity({"prCommitSha": "sha-abc", "argocdNamespace": "argocd"})
        assert context.pr_commit_sha == "sha-abc"

    def test_missing_pr_commit_sha_yields_none(self) -> None:
        context = parse_cluster_identity({})
        assert context.pr_commit_sha is None


class TestBuildInitialInputs:
    def test_initial_inputs_seeded_from_context_sha(self) -> None:
        inputs = build_initial_inputs(ClusterContext(argocd_namespace="argocd", pr_commit_sha="sha-abc"), dry_run=False)
        assert inputs.previous_commit_sha == "sha-abc"
        assert inputs.previous_state == ConvergenceState()
        assert inputs.previous_sent_status is None

    def test_dry_run_propagates_into_initial_inputs(self) -> None:
        inputs = build_initial_inputs(ClusterContext(argocd_namespace="argocd", pr_commit_sha="sha-1"), dry_run=True)
        assert inputs.dry_run is True
