from dataclasses import dataclass, field
from pathlib import Path

import yaml

from k8s_validator.config import REPO_ROOT, settings


@dataclass
class KustomizeOverlay:
    path: Path


@dataclass
class HelmChart:
    name: str
    repo_url: str
    version: str
    value_files: list[Path] = field(default_factory=list)


def discover_kustomize_overlays() -> list[KustomizeOverlay]:
    gitops_root = REPO_ROOT / settings.rendering.gitops_root
    overlays = []
    for kustomization in sorted(gitops_root.rglob("kustomization.yaml")):
        if kustomization.parent.name == "base":
            continue
        with open(kustomization, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data and data.get("kind") == "Component":
            continue
        overlays.append(KustomizeOverlay(path=kustomization.parent))
    return overlays


def discover_helm_charts() -> list[HelmChart]:
    appsets_dir = REPO_ROOT / settings.rendering.appsets_dir
    charts = []
    for appset_file in sorted(appsets_dir.glob("*-helm-appset.yaml")):
        with open(appset_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        sources = data["spec"]["template"]["spec"]["sources"]
        chart_source = sources[0]

        value_files: list[Path] = []
        for source in sources:
            if "ref" in source:
                continue
            helm = source.get("helm", {})
            for vf in helm.get("valueFiles", []):
                stripped = vf.removeprefix("$values/")
                value_files.append(REPO_ROOT / stripped)

        charts.append(
            HelmChart(
                name=chart_source["chart"],
                repo_url=chart_source["repoURL"],
                version=chart_source["targetRevision"],
                value_files=value_files,
            )
        )
    return charts
