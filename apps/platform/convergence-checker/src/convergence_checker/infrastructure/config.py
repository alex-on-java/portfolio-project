from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dynaconf import Dynaconf

from convergence_checker.application import RuntimeSettings

SERVICE_ACCOUNT_NAMESPACE_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


@dataclass(frozen=True, slots=True)
class GithubAppSettings:
    owner_repo: str
    app_id: str | None
    private_key: str | None
    installation_id: str | None

    @property
    def posting_enabled(self) -> bool:
        return self.app_id is not None and self.private_key is not None and self.installation_id is not None


@dataclass(frozen=True, slots=True)
class KubernetesSettings:
    cluster_identity_namespace: str
    cluster_identity_configmap_name: str
    heartbeat_namespace: str
    heartbeat_configmap_name: str
    field_manager_name: str


@dataclass(frozen=True, slots=True)
class AppSettings:
    runtime: RuntimeSettings
    kubernetes: KubernetesSettings
    github: GithubAppSettings


def load_settings(
    *,
    settings_path: Path | None = None,
    namespace_path: Path = SERVICE_ACCOUNT_NAMESPACE_PATH,
) -> AppSettings:
    dynaconf_settings = Dynaconf(
        envvar_prefix="CONVERGENCE_CHECKER",
        settings_files=[settings_path or Path("settings.toml")],
        load_dotenv=False,
    )

    runtime = RuntimeSettings(
        check_interval_seconds=_required_int(dynaconf_settings, "check_interval_seconds"),
        stability_threshold=_required_int(dynaconf_settings, "stability_threshold"),
        safety_timeout_seconds=_required_int(dynaconf_settings, "safety_timeout_seconds"),
    )
    kubernetes = KubernetesSettings(
        cluster_identity_namespace=_required_str(dynaconf_settings, "cluster_identity_namespace"),
        cluster_identity_configmap_name=_required_str(dynaconf_settings, "cluster_identity_configmap_name"),
        heartbeat_namespace=_read_namespace(namespace_path),
        heartbeat_configmap_name=_required_str(dynaconf_settings, "heartbeat_configmap_name"),
        field_manager_name=_required_str(dynaconf_settings, "field_manager_name"),
    )
    github = GithubAppSettings(
        owner_repo=_required_str(dynaconf_settings, "owner_repo"),
        app_id=_optional_env_str("GITHUB_APP_ID"),
        private_key=_optional_env_str("GITHUB_APP_PRIVATE_KEY"),
        installation_id=_optional_env_str("GITHUB_APP_INSTALLATION_ID"),
    )
    return AppSettings(runtime=runtime, kubernetes=kubernetes, github=github)


def _required_str(settings: Dynaconf, name: str) -> str:
    value = settings.get(name)
    if not isinstance(value, str) or value == "":
        msg = f"Missing required setting: {name}"
        raise ValueError(msg)
    return value


def _optional_env_str(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value


def _required_int(settings: Dynaconf, name: str) -> int:
    value = settings.get(name)
    if not isinstance(value, int):
        msg = f"Missing required integer setting: {name}"
        raise TypeError(msg)
    return value


def _read_namespace(namespace_path: Path) -> str:
    try:
        namespace = namespace_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        msg = f"Missing service-account namespace file: {namespace_path}"
        raise ValueError(msg) from exc
    if namespace == "":
        msg = f"Service-account namespace file is empty: {namespace_path}"
        raise ValueError(msg)
    return namespace
