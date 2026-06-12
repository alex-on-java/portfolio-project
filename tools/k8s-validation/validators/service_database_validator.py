from pathlib import Path

import yaml

from k8s_validator.config import REPO_ROOT

SERVICE_DATABASE = (
    REPO_ROOT
    / "gitops"
    / "datastores"
    / "cnpg-eso-verification"
    / "components"
    / "service-database"
)
BASE_KUSTOMIZATION = (
    REPO_ROOT
    / "gitops"
    / "datastores"
    / "cnpg-eso-verification"
    / "base"
    / "kustomization.yaml"
)
SERVICE_COMPONENT_PREFIX = "../components/service-database/"
LEGACY_GENERATOR_PATHS = [
    SERVICE_DATABASE / "generate.py",
    SERVICE_DATABASE / "services.yaml",
    SERVICE_DATABASE / "generated",
    SERVICE_DATABASE / "templates",
]
SHARED_FILES = [
    "kustomization.yaml",
    "external-secrets.yaml",
    "database.yaml",
    "provisioning-job.yaml",
    "managed-roles-patch.yaml",
]


def _load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _base_services() -> list[str]:
    base = _load_yaml(BASE_KUSTOMIZATION)
    services = []
    for component in base["components"]:
        assert component != "../components/service-database/generated"
        if component.startswith(SERVICE_COMPONENT_PREFIX):
            services.append(component.removeprefix(SERVICE_COMPONENT_PREFIX))
    return services


def validate_service_database_declarative_inventory():
    for path in LEGACY_GENERATOR_PATHS:
        assert not path.exists(), f"legacy generator path must be removed: {path}"

    for name in SHARED_FILES:
        assert (SERVICE_DATABASE / "_shared" / name).is_file()

    services = _base_services()
    assert services, "base must wire at least one service database component"
    assert len(services) == len(set(services)), "base wires a service more than once"

    service_dirs = {
        path.name
        for path in SERVICE_DATABASE.iterdir()
        if path.is_dir() and not path.name.startswith("_")
    }
    assert service_dirs == set(services)

    for service in services:
        service_dir = SERVICE_DATABASE / service
        values = _load_yaml(service_dir / "values.yaml")
        component = _load_yaml(service_dir / "kustomization.yaml")

        assert values["metadata"]["name"] == f"cnpg-service-values-{service}"
        assert values["data"]["serviceName"] == service
        assert (
            values["metadata"]["annotations"]["config.kubernetes.io/local-config"]
            == "true"
        )
        assert component["resources"] == ["values.yaml"]
        assert component["components"] == ["../_shared"]
