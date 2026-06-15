import subprocess
from pathlib import Path

import pytest
import yaml

from k8s_validator.config import REPO_ROOT


ARGOCD_CHART_VERSION = "9.4.11"
BOOTSTRAP_OVERLAYS = [
    REPO_ROOT / "gitops/platform/argocd/bootstrap/overlays/ephemeral",
    REPO_ROOT / "gitops/platform/argocd/bootstrap/overlays/main",
]
TIMEOUT_KEYS = {
    "timeout.reconciliation",
    "timeout.reconciliation.jitter",
    "timeout.hard.reconciliation",
}


def _load_docs(text: str) -> list[dict]:
    return [doc for doc in yaml.safe_load_all(text) if isinstance(doc, dict)]


def _render_kustomize(path: Path) -> list[dict]:
    result = subprocess.run(
        ["kubectl", "kustomize", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"kubectl kustomize failed for {path}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return _load_docs(result.stdout)


def _argocd_cm(docs: list[dict]) -> list[dict]:
    return [
        doc
        for doc in docs
        if doc.get("kind") == "ConfigMap"
        and doc.get("metadata", {}).get("name") == "argocd-cm"
    ]


def _infra_root() -> Path | None:
    candidates = (
        REPO_ROOT.parent / "portfolio-project-infra",
        REPO_ROOT.parents[1] / "portfolio-project-infra",
    )
    return next((path for path in candidates if path.exists()), None)


def _argocd_helm_values(reconciliation_timeout: str) -> dict:
    seconds = reconciliation_timeout.removesuffix("s")
    return {
        "configs": {
            "cm": {"create": False},
            "params": {"server.insecure": False},
        },
        "controller": {
            "extraArgs": [
                f"--app-resync={seconds}",
                "--app-resync-jitter=60",
            ],
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                }
            },
        },
        "repoServer": {
            "extraArgs": [
                f"--revision-cache-expiration={reconciliation_timeout}",
            ],
            "resources": {
                "requests": {
                    "cpu": "100m",
                    "memory": "256Mi",
                }
            },
        },
    }


def _render_argocd_helm(tmp_path: Path, reconciliation_timeout: str) -> list[dict]:
    values_file = tmp_path / f"argocd-{reconciliation_timeout}.yaml"
    values_file.write_text(
        yaml.safe_dump(_argocd_helm_values(reconciliation_timeout), sort_keys=True),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "helm",
            "template",
            "argocd",
            "argo-cd",
            "--repo",
            "https://argoproj.github.io/argo-helm",
            "--version",
            ARGOCD_CHART_VERSION,
            "--namespace",
            "argocd",
            "-f",
            str(values_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "helm template failed for infra-equivalent ArgoCD values\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    return _load_docs(result.stdout)


def _container_args(docs: list[dict], name: str) -> list[str]:
    workloads = [
        doc
        for doc in docs
        if doc.get("kind") in {"Deployment", "StatefulSet"}
        and doc.get("metadata", {}).get("name") == name
    ]
    assert len(workloads) == 1, f"expected exactly one workload named {name}"
    containers = workloads[0]["spec"]["template"]["spec"]["containers"]
    return containers[0].get("args", [])


def validate_gitops_bootstrap_argocd_cm_contract():
    for overlay in BOOTSTRAP_OVERLAYS:
        cms = _argocd_cm(_render_kustomize(overlay))
        assert len(cms) == 1, f"{overlay} must render exactly one argocd-cm"

        cm = cms[0]
        metadata = cm.get("metadata", {})
        data = cm.get("data", {})

        assert metadata.get("namespace") == "argocd"
        assert metadata.get("labels", {}).get("app.kubernetes.io/part-of") == "argocd"
        assert (
            metadata.get("annotations", {}).get("argocd.argoproj.io/sync-wave") == "-90"
        )

        assert not TIMEOUT_KEYS.intersection(data)
        assert "resource.customizations.health.postgresql.cnpg.io_Database" not in data

        assert data.get("application.instanceLabelKey") == "argocd.argoproj.io/instance"
        assert "resource.exclusions" in data
        assert "resource.customizations.ignoreResourceUpdates.all" in data


def validate_main_bootstrap_overlay_only_renders_argocd_cm():
    docs = _render_kustomize(
        REPO_ROOT / "gitops/platform/argocd/bootstrap/overlays/main"
    )
    assert len(docs) == 1
    assert docs[0].get("kind") == "ConfigMap"
    assert docs[0].get("metadata", {}).get("name") == "argocd-cm"


def validate_argocd_cm_health_check_source_layout():
    source_dir = REPO_ROOT / "gitops/platform/argocd/bootstrap/base/argocd-cm"
    health_dir = source_dir / "resource-health"

    assert health_dir.is_dir()
    assert not (health_dir / "postgresql.cnpg.io_Database.lua").exists()

    kustomization = (source_dir / "kustomization.yaml").read_text(encoding="utf-8")
    assert (
        "resource.customizations.health.postgresql.cnpg.io_Database"
        not in kustomization
    )


def validate_infra_argocd_module_source_contract():
    infra_root = _infra_root()
    if infra_root is None:
        pytest.skip("private portfolio-project-infra sibling repo is not checked out")

    module_main = (infra_root / "infra/modules/argocd/main.tf").read_text(
        encoding="utf-8"
    )
    module_variables = (infra_root / "infra/modules/argocd/variables.tf").read_text(
        encoding="utf-8"
    )

    assert "timeout.reconciliation" not in module_main
    assert "create = false" in module_main
    assert "--app-resync=${local.reconciliation_timeout_seconds}" in module_main
    assert "--app-resync-jitter=60" in module_main
    assert "--revision-cache-expiration=${var.reconciliation_timeout}" in module_main
    assert 'regex("^[0-9]+s$", var.reconciliation_timeout)' in module_variables


def validate_infra_argocd_helm_rendering_contract(tmp_path):
    for reconciliation_timeout in ("30s", "180s"):
        docs = _render_argocd_helm(tmp_path, reconciliation_timeout)
        seconds = reconciliation_timeout.removesuffix("s")

        assert not _argocd_cm(docs)
        assert f"--app-resync={seconds}" in _container_args(
            docs, "argocd-application-controller"
        )
        assert "--app-resync-jitter=60" in _container_args(
            docs, "argocd-application-controller"
        )
        assert (
            f"--revision-cache-expiration={reconciliation_timeout}"
            in _container_args(docs, "argocd-repo-server")
        )
