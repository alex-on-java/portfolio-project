import subprocess
from pathlib import Path

import yaml

from k8s_validator.cache import chart_key
from k8s_validator.config import REPO_ROOT
from k8s_validator.discovery import HelmChart, KustomizeOverlay


def _sanitize_path(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT)
    return str(relative).replace("/", "-").replace(".", "-")


def _filter_crds(text: str) -> str:
    docs = []
    for doc in yaml.safe_load_all(text):
        if not doc or not isinstance(doc, dict):
            continue
        if doc.get("kind") == "CustomResourceDefinition":
            continue
        docs.append(doc)
    if not docs:
        return ""
    return yaml.dump_all(docs, default_flow_style=False)


def render_kustomize(overlay: KustomizeOverlay, output_dir: Path) -> Path | None:
    result = subprocess.run(
        ["kubectl", "kustomize", str(overlay.path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"kubectl kustomize failed for {overlay.path}:\n{result.stderr}"
        )

    filtered = _filter_crds(result.stdout)
    if not filtered.strip():
        return None

    filename = f"kustomize--{_sanitize_path(overlay.path)}.yaml"
    out_path = output_dir / filename
    out_path.write_text(filtered)
    return out_path


def render_helm(chart: HelmChart, chart_path: Path, output_dir: Path) -> Path | None:
    cmd = ["helm", "template", chart.name, str(chart_path)]
    for vf in chart.value_files:
        cmd.extend(["-f", str(vf)])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"helm template failed for {chart.name}:\n{result.stderr}")

    filtered = _filter_crds(result.stdout)
    if not filtered.strip():
        return None

    filename = f"helm--{chart.name}-{chart.version}.yaml"
    out_path = output_dir / filename
    out_path.write_text(filtered)
    return out_path


def render_all(
    overlays: list[KustomizeOverlay],
    charts: list[HelmChart],
    chart_paths: dict[str, Path],
    output_dir: Path,
) -> Path:
    for overlay in overlays:
        render_kustomize(overlay, output_dir)

    for chart in charts:
        path = chart_paths.get(chart_key(chart))
        if path:
            render_helm(chart, path, output_dir)

    return output_dir
