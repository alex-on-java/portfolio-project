import json
import subprocess

import pytest

from k8s_validator.cache import ensure_all_charts_cached
from k8s_validator.config import KUBERNETES_VERSION, REPO_ROOT, settings
from k8s_validator.discovery import discover_helm_charts, discover_kustomize_overlays
from k8s_validator.rendering import render_all
from k8s_validator.schemas import (
    coverage_gate,
    crd_schema_kubeconform_template,
    download_builtin_schemas,
    generate_all_schemas,
    k8s_schema_kubeconform_template,
)


def run_cli_json(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError) as exc:
        raise AssertionError(
            f"{cmd[0]} produced non-JSON output (exit code {result.returncode}).\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}\n"
            f"Parse error: {exc}"
        ) from exc


@pytest.fixture(scope="session")
def helm_chart_paths():
    charts = discover_helm_charts()
    return charts, ensure_all_charts_cached(charts)


@pytest.fixture(scope="session")
def rendered_manifests_dir(helm_chart_paths, tmp_path_factory):
    charts, chart_paths = helm_chart_paths
    overlays = discover_kustomize_overlays()
    output_dir = tmp_path_factory.mktemp("k8s-rendered")
    return render_all(overlays, charts, chart_paths, output_dir)


@pytest.fixture(scope="session")
def crd_schemas_dir(helm_chart_paths, rendered_manifests_dir):
    charts, chart_paths = helm_chart_paths
    schemas_dir = generate_all_schemas(charts, chart_paths)
    uncovered = coverage_gate(rendered_manifests_dir, schemas_dir)
    if uncovered:
        pytest.fail(
            f"CRD schema coverage gap — {len(uncovered)} GVK(s) have no schema:\n"
            + "\n".join(f"  {gvk}" for gvk in uncovered)
        )
    return schemas_dir


@pytest.fixture(scope="session")
def k8s_schemas_dir(rendered_manifests_dir):
    return download_builtin_schemas(
        rendered_manifests_dir,
        KUBERNETES_VERSION,
    )


@pytest.fixture(scope="session")
def kyverno_policies_dir():
    return REPO_ROOT / settings.kyverno.policies_dir


@pytest.fixture(scope="session")
def kubeconform_settings(crd_schemas_dir, k8s_schemas_dir):
    return {
        "kubernetes_version": KUBERNETES_VERSION,
        "schema_locations": [
            str(k8s_schemas_dir) + "/" + k8s_schema_kubeconform_template(),
            str(crd_schemas_dir) + "/" + crd_schema_kubeconform_template(),
        ],
        "skip_kinds": settings.kubeconform.skip_kinds,
    }
