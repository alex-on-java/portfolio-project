import subprocess
from pathlib import Path

from k8s_validator.config import REPO_ROOT, settings
from k8s_validator.discovery import HelmChart


def _is_oci(repo_url: str) -> bool:
    return repo_url.startswith("oci://") or repo_url.startswith("ghcr.io")


def _chart_cache_dir(chart: HelmChart) -> Path:
    return (
        REPO_ROOT / settings.rendering.helm_cache_dir / f"{chart.name}-{chart.version}"
    )


def ensure_chart_cached(chart: HelmChart) -> Path:
    cache_dir = _chart_cache_dir(chart)
    chart_dir = cache_dir / chart.name
    if chart_dir.is_dir():
        return chart_dir

    cache_dir.mkdir(parents=True, exist_ok=True)

    if _is_oci(chart.repo_url):
        url = chart.repo_url
        if not url.startswith("oci://"):
            url = f"oci://{url}"
        cmd = [
            "helm",
            "pull",
            f"{url}/{chart.name}",
            "--version",
            chart.version,
            "--untar",
            "-d",
            str(cache_dir),
        ]
    else:
        cmd = [
            "helm",
            "pull",
            chart.name,
            "--repo",
            chart.repo_url,
            "--version",
            chart.version,
            "--untar",
            "-d",
            str(cache_dir),
        ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return chart_dir


def chart_key(chart: HelmChart) -> str:
    return f"{chart.name}@{chart.version}"


def ensure_all_charts_cached(charts: list[HelmChart]) -> dict[str, Path]:
    keys = [chart_key(c) for c in charts]
    if len(keys) != len(set(keys)):
        dupes = [k for k in keys if keys.count(k) > 1]
        raise ValueError(f"Duplicate chart keys detected: {set(dupes)}")
    return {chart_key(c): ensure_chart_cached(c) for c in charts}
