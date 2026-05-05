from __future__ import annotations

from pathlib import Path
from typing import Any

from attrs import frozen
from dynaconf import Dynaconf, Validator

_EDITABLE_DEV_SETTINGS = Path(__file__).resolve().parent.parent.parent.parent / "settings.toml"

_REQUIRED_STRINGS = (
    "cluster_identity_namespace",
    "cluster_identity_configmap_name",
    "heartbeat_configmap_name",
    "field_manager_name",
    "owner_repo",
    "github_status_context",
)

_REQUIRED_POSITIVE_INTEGERS = (
    "check_interval_seconds",
    "stability_threshold",
    "safety_timeout_seconds",
)


@frozen
class ClusterSettings:
    cluster_identity_namespace: str
    cluster_identity_configmap_name: str
    heartbeat_configmap_name: str
    field_manager_name: str


@frozen
class GitHubSettings:
    owner_repo: str
    github_status_context: str


@frozen
class LoopSettings:
    check_interval_seconds: int
    stability_threshold: int
    safety_timeout_seconds: int


@frozen
class RuntimeSettings:
    cluster: ClusterSettings
    github: GitHubSettings
    loop: LoopSettings


def _non_empty(value: str) -> bool:
    return bool(value.strip())


def _positive(value: int) -> bool:
    return value > 0


def build_settings() -> Dynaconf:
    config = Dynaconf(
        settings_files=[
            "/app/settings.toml",
            str(_EDITABLE_DEV_SETTINGS),
        ],
        envvar_prefix="CONVERGENCE_CHECKER",
    )
    register_validators(config)
    return config


def register_validators(config: Dynaconf) -> None:
    config.validators.register(
        *(Validator(name, must_exist=True, is_type_of=str, condition=_non_empty) for name in _REQUIRED_STRINGS),
        *(
            Validator(name, must_exist=True, is_type_of=int, condition=_positive)
            for name in _REQUIRED_POSITIVE_INTEGERS
        ),
    )


def load_settings(config: Dynaconf | None = None) -> RuntimeSettings:
    source = config if config is not None else build_settings()
    if config is not None:
        register_validators(source)
    source.validators.validate()
    values: dict[str, Any] = {
        name: getattr(source, name) for name in (*_REQUIRED_STRINGS, *_REQUIRED_POSITIVE_INTEGERS)
    }
    return RuntimeSettings(
        cluster=ClusterSettings(
            cluster_identity_namespace=values["cluster_identity_namespace"],
            cluster_identity_configmap_name=values["cluster_identity_configmap_name"],
            heartbeat_configmap_name=values["heartbeat_configmap_name"],
            field_manager_name=values["field_manager_name"],
        ),
        github=GitHubSettings(
            owner_repo=values["owner_repo"],
            github_status_context=values["github_status_context"],
        ),
        loop=LoopSettings(
            check_interval_seconds=values["check_interval_seconds"],
            stability_threshold=values["stability_threshold"],
            safety_timeout_seconds=values["safety_timeout_seconds"],
        ),
    )
