import subprocess
from pathlib import Path
from typing import Any

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
BASE = REPO_ROOT / "gitops" / "datastores" / "cnpg-eso-verification" / "base"
SERVICE_COMPONENT_PREFIX = "../components/service-database/"
CLUSTER_NAME = "cnpg-eso-multidb-verification"
SQL_CONFIG_MAP_NAME = "cnpg-verification-provisioning-sql"
LEGACY_GENERATOR_PATHS = [
    SERVICE_DATABASE / "generate.py",
    SERVICE_DATABASE / "services.yaml",
    SERVICE_DATABASE / "generated",
    SERVICE_DATABASE / "templates",
]
PLACEHOLDER_FRAGMENTS = [
    "ROLE0_",
    "ROLE1_",
    "ROLE2_",
    "ROLE3_",
    "ROLE4_",
    "ROLE5_",
    "ROLE6_",
    "ROLE7_",
    "ROLE8_",
    "SERVICE_SECRET_",
    "cnpg-eso-service",
    "cnpg-verification-service-",
    "cnpg-verification-provision-service",
    "provision-service.sql",
    "service_app",
]
SHARED_FILES = [
    "kustomization.yaml",
    "external-secrets.yaml",
    "database.yaml",
    "provisioning-job.yaml",
    "managed-roles-patch.yaml",
]
SECRET_ROLE_KEYS = {
    "secretRoA": "roleAppRoA",
    "secretRoB": "roleAppRoB",
    "secretRwA": "roleAppRwA",
    "secretRwB": "roleAppRwB",
    "secretMigA": "roleAppMigA",
}
LOGIN_ROLE_GROUP_KEYS = {
    "roleAppRoA": "roleAppRo",
    "roleAppRoB": "roleAppRo",
    "roleAppRwA": "roleAppRw",
    "roleAppRwB": "roleAppRw",
    "roleAppMigA": "roleAppMig",
}
LOGIN_ROLE_SECRET_KEYS = {
    "roleAppRoA": "secretRoA",
    "roleAppRoB": "secretRoB",
    "roleAppRwA": "secretRwA",
    "roleAppRwB": "secretRwB",
    "roleAppMigA": "secretMigA",
}
STABLE_ROLE_KEYS = ["roleApp", "roleAppRo", "roleAppRw", "roleAppMig"]
LOGIN_ROLE_KEYS = [
    "roleAppRoA",
    "roleAppRoB",
    "roleAppRwA",
    "roleAppRwB",
    "roleAppMigA",
]


def _load_yaml(path: Path):
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_base() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["kubectl", "kustomize", str(BASE)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [
        doc
        for doc in yaml.safe_load_all(result.stdout)
        if isinstance(doc, dict) and doc.get("kind")
    ]


def _base_services() -> list[str]:
    base = _load_yaml(BASE_KUSTOMIZATION)
    services = []
    for component in base["components"]:
        assert component != "../components/service-database/generated"
        if component.startswith(SERVICE_COMPONENT_PREFIX):
            services.append(component.removeprefix(SERVICE_COMPONENT_PREFIX))
    return services


def _doc_key(doc: dict[str, Any]) -> tuple[str, str]:
    return doc["kind"], doc["metadata"]["name"]


def _rendered_by_key(
    docs: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {_doc_key(doc): doc for doc in docs}


def _values_by_service(services: list[str]) -> dict[str, dict[str, str]]:
    return {
        service: _load_yaml(SERVICE_DATABASE / service / "values.yaml")["data"]
        for service in services
    }


def _find_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _find_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _find_strings(child)


def _assert_no_placeholders(docs: list[dict[str, Any]]):
    for doc in docs:
        name = doc["metadata"]["name"]
        for value in _find_strings(doc):
            for fragment in PLACEHOLDER_FRAGMENTS:
                assert fragment not in value, (
                    f"{doc['kind']}/{name} still contains placeholder {fragment}: {value}"
                )


def _env(container: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in container["env"] if item["name"] == name)


def _role_by_name(cluster: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {role["name"]: role for role in cluster["spec"]["managed"]["roles"]}


def _assert_rendered_database(
    rendered: dict[tuple[str, str], dict[str, Any]], values: dict[str, str]
):
    database = rendered[("Database", values["databaseResourceName"])]
    assert database["spec"]["cluster"]["name"] == CLUSTER_NAME
    assert database["spec"]["name"] == values["databaseName"]
    assert database["spec"]["owner"] == values["databaseOwner"]
    assert database["spec"]["ensure"] == "present"
    assert database["spec"]["databaseReclaimPolicy"] == "retain"
    assert database["spec"]["schemas"] == [
        {
            "name": values["schemaName"],
            "owner": values["schemaOwner"],
            "ensure": "present",
        }
    ]


def _assert_rendered_external_secrets(
    rendered: dict[tuple[str, str], dict[str, Any]], values: dict[str, str]
):
    for secret_key, role_key in SECRET_ROLE_KEYS.items():
        secret_name = values[secret_key]
        external_secret = rendered[("ExternalSecret", secret_name)]
        assert external_secret["spec"]["refreshInterval"] == "0s"
        assert external_secret["spec"]["refreshPolicy"] == "CreatedOnce"
        assert external_secret["spec"]["target"]["name"] == secret_name
        assert external_secret["spec"]["target"]["creationPolicy"] == "Owner"
        template = external_secret["spec"]["target"]["template"]
        assert template["type"] == "kubernetes.io/basic-auth"
        assert template["metadata"]["labels"]["cnpg.io/reload"] == "true"
        assert template["data"]["username"] == values[role_key]


def _assert_rendered_job(
    rendered: dict[tuple[str, str], dict[str, Any]], values: dict[str, str]
):
    job = rendered[("Job", values["provisionJobName"])]
    container = job["spec"]["template"]["spec"]["containers"][0]
    assert _env(container, "PGDATABASE")["value"] == values["databaseName"]
    assert _env(container, "PGUSER")["value"] == values["roleAppMigA"]
    assert (
        _env(container, "PGPASSWORD")["valueFrom"]["secretKeyRef"]["name"]
        == values["secretMigA"]
    )
    assert _env(container, "PGOPTIONS")["value"] == f"-c role={values['roleApp']}"
    assert f"--file=/sql/{values['provisionSqlKey'].strip()}" in container["command"][2]


def _assert_rendered_sql(
    rendered: dict[tuple[str, str], dict[str, Any]], values: dict[str, str]
):
    config_map = rendered[("ConfigMap", SQL_CONFIG_MAP_NAME)]
    assert (
        config_map["data"][values["provisionSqlKey"].strip()] == values["provisionSql"]
    )


def _assert_rendered_roles(roles: dict[str, dict[str, Any]], values: dict[str, str]):
    for role_key in STABLE_ROLE_KEYS + LOGIN_ROLE_KEYS:
        assert values[role_key] in roles

    owner = roles[values["roleApp"]]
    assert owner["ensure"] == "present"
    assert owner["login"] is False
    assert owner["inherit"] is False

    for role_key in ["roleAppRo", "roleAppRw"]:
        role = roles[values[role_key]]
        assert role["ensure"] == "present"
        assert role["login"] is False
        assert role["inherit"] is False

    migration_group = roles[values["roleAppMig"]]
    assert migration_group["ensure"] == "present"
    assert migration_group["login"] is False
    assert migration_group["inherit"] is False
    assert migration_group["inRoles"] == [values["roleApp"]]

    for role_key in LOGIN_ROLE_KEYS:
        role = roles[values[role_key]]
        assert role["ensure"] == "present"
        assert role["login"] is True
        assert role["inherit"] is True
        assert role["connectionLimit"] == -1
        assert role["inRoles"] == [values[LOGIN_ROLE_GROUP_KEYS[role_key]]]
        assert (
            role["passwordSecret"]["name"] == values[LOGIN_ROLE_SECRET_KEYS[role_key]]
        )


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


def validate_service_database_rendered_contract():
    services = _base_services()
    values_by_service = _values_by_service(services)
    docs = _render_base()
    rendered = _rendered_by_key(docs)
    _assert_no_placeholders(docs)

    cluster = rendered[("Cluster", CLUSTER_NAME)]
    roles = _role_by_name(cluster)

    assert {
        doc["metadata"]["name"]
        for doc in docs
        if doc["kind"] == "Database" and doc["metadata"]["name"].startswith("cnpg-eso-")
    } == {values["databaseResourceName"] for values in values_by_service.values()}

    for values in values_by_service.values():
        _assert_rendered_database(rendered, values)
        _assert_rendered_external_secrets(rendered, values)
        _assert_rendered_job(rendered, values)
        _assert_rendered_sql(rendered, values)
        _assert_rendered_roles(roles, values)
