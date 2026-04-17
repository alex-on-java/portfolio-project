import copy
import json
import os
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from k8s_validator.cache import chart_key
from k8s_validator.config import REPO_ROOT, settings
from k8s_validator.discovery import HelmChart

_DOWNLOAD_TIMEOUT_SECONDS = 10


def _download_atomic(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with (
            urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response,
            open(tmp, "wb") as out,
        ):
            shutil.copyfileobj(response, out)
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


BUILTIN_API_GROUPS = frozenset(
    {
        "",
        "apps",
        "batch",
        "networking.k8s.io",
        "rbac.authorization.k8s.io",
        "policy",
        "autoscaling",
        "apiextensions.k8s.io",
        "admissionregistration.k8s.io",
        "certificates.k8s.io",
        "coordination.k8s.io",
        "discovery.k8s.io",
        "events.k8s.io",
        "scheduling.k8s.io",
        "storage.k8s.io",
    }
)


def crd_schema_filename(kind: str, group: str, version: str) -> str:
    return f"{kind.lower()}-{group}-{version}.json"


def crd_schema_kubeconform_template() -> str:
    return "{{.ResourceKind}}-{{.Group}}-{{.ResourceAPIVersion}}.json"


def k8s_schema_filename(kind: str, group: str, version: str) -> str:
    if group:
        first_label = group.split(".")[0]
        return f"{kind.lower()}-{first_label}-{version}.json"
    return f"{kind.lower()}-{version}.json"


def k8s_schema_kubeconform_template() -> str:
    return (
        "{{.NormalizedKubernetesVersion}}-standalone-strict"
        "/{{.ResourceKind}}{{.KindSuffix}}.json"
    )


def _convert_schema(schema: dict) -> dict:
    schema = copy.deepcopy(schema)
    return _transform(schema)


def _transform(node: Any) -> Any:
    if not isinstance(node, dict):
        return node

    if node.get("x-kubernetes-int-or-string"):
        node.pop("x-kubernetes-int-or-string", None)
        node.pop("type", None)
        node["oneOf"] = [{"type": "integer"}, {"type": "string"}]

    if node.get("x-kubernetes-preserve-unknown-fields"):
        node.pop("x-kubernetes-preserve-unknown-fields", None)
        if "properties" in node:
            node["additionalProperties"] = True

    for key in [k for k in node if k.startswith("x-kubernetes-")]:
        del node[key]

    if "properties" in node:
        node["properties"] = {k: _transform(v) for k, v in node["properties"].items()}
    if isinstance(node.get("items"), dict):
        node["items"] = _transform(node["items"])
    if isinstance(node.get("additionalProperties"), dict):
        node["additionalProperties"] = _transform(node["additionalProperties"])

    return node


def _extract_crds_from_yaml(text: str) -> list[dict]:
    crds = []
    for doc in yaml.safe_load_all(text):
        if not doc or not isinstance(doc, dict):
            continue
        if doc.get("kind") == "CustomResourceDefinition":
            crds.append(doc)
    return crds


def _crd_to_schemas(crd: dict) -> list[tuple[str, str, str, dict]]:
    group = crd["spec"]["group"]
    kind = crd["spec"]["names"]["kind"]
    results = []
    for ver in crd["spec"].get("versions", []):
        version = ver["name"]
        raw = ver.get("schema", {}).get("openAPIV3Schema")
        if not raw:
            continue
        converted = _convert_schema(raw)
        converted["$schema"] = "http://json-schema.org/draft-07/schema#"
        results.append((kind, group, version, converted))
    return results


def _write_schemas(schemas: list[tuple[str, str, str, dict]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for kind, group, version, schema in schemas:
        filename = crd_schema_filename(kind, group, version)
        with open(output_dir / filename, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=2)


def extract_from_charts(
    charts: list[HelmChart],
    chart_paths: dict[str, Path],
) -> list[tuple[str, str, str, dict]]:
    all_schemas = []
    name_to_key = {c.name: chart_key(c) for c in charts}
    for entry in settings.schemas.from_charts:
        chart_name = entry["chart"]
        key = name_to_key.get(chart_name)
        if not key:
            raise ValueError(
                f"schemas.from_charts entry references chart {chart_name!r}, "
                f"but no such chart was discovered. "
                f"Known charts: {sorted(name_to_key)}"
            )
        chart_path = chart_paths.get(key)
        if not chart_path:
            raise ValueError(
                f"schemas.from_charts entry for chart {chart_name!r} resolved "
                f"to cache key {key!r}, but no cached chart path is available. "
                f"Known cache keys: {sorted(chart_paths)}"
            )

        cmd = ["helm", "template", "--include-crds", chart_name, str(chart_path)]
        helm_sets = entry.get("crd_helm_sets", {})
        for helm_key, helm_val in helm_sets.items():
            cmd.extend(["--set", f"{helm_key}={helm_val}"])

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for crd in _extract_crds_from_yaml(result.stdout):
            all_schemas.extend(_crd_to_schemas(crd))
    return all_schemas


def extract_from_releases() -> list[tuple[str, str, str, dict]]:
    all_schemas = []
    cache_dir = REPO_ROOT / ".cache" / "release-assets"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for entry in settings.schemas.from_releases:
        name = entry["name"]
        version = entry["version"]

        if "url" in entry:
            url = entry["url"]
            asset = url.rsplit("/", 1)[-1]
        else:
            repo = entry["repo"]
            asset = entry["asset"]
            url = f"https://github.com/{repo}/releases/download/{version}/{asset}"

        cached_file = cache_dir / f"{name}-{version}" / asset
        if not cached_file.exists():
            cached_file.parent.mkdir(parents=True, exist_ok=True)
            _download_atomic(url, cached_file)

        text = cached_file.read_text()
        for crd in _extract_crds_from_yaml(text):
            all_schemas.extend(_crd_to_schemas(crd))
    return all_schemas


def generate_all_schemas(charts: list[HelmChart], chart_paths: dict[str, Path]) -> Path:
    output_dir = REPO_ROOT / settings.schemas.output_dir

    resolved = output_dir.resolve()
    cache_root = (REPO_ROOT / ".cache").resolve()
    if not resolved.is_relative_to(cache_root) or resolved == cache_root:
        raise ValueError(
            f"schemas.output_dir must be a subdirectory of .cache/: got {output_dir}"
        )

    if output_dir.exists():
        shutil.rmtree(output_dir)

    schemas = extract_from_charts(charts, chart_paths)
    schemas.extend(extract_from_releases())
    _write_schemas(schemas, output_dir)
    return output_dir


def download_builtin_schemas(rendered_dir: Path, k8s_version: str) -> Path:
    repo_url = settings.schemas.k8s_schema_repo_url
    version_dir = f"v{k8s_version}-standalone-strict"
    output_dir = REPO_ROOT / settings.schemas.k8s_schemas_dir / version_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for manifest_file in sorted(rendered_dir.glob("*.yaml")):
        text = manifest_file.read_text(encoding="utf-8")
        for doc in yaml.safe_load_all(text):
            if not doc or not isinstance(doc, dict):
                continue
            api_version = doc.get("apiVersion", "")
            kind = doc.get("kind", "")
            if not kind:
                continue
            group, version = parse_api_version(api_version)
            if group not in BUILTIN_API_GROUPS:
                continue

            filename = k8s_schema_filename(kind, group, version)
            schema_file = output_dir / filename
            if schema_file.exists():
                continue

            url = f"{repo_url}/{version_dir}/{filename}"
            _download_atomic(url, schema_file)

    return REPO_ROOT / settings.schemas.k8s_schemas_dir


def parse_api_version(api_version: str) -> tuple[str, str]:
    if "/" in api_version:
        group, version = api_version.rsplit("/", 1)
        return group, version
    return "", api_version


def coverage_gate(rendered_dir: Path, schemas_dir: Path) -> list[str]:
    rendered_gvks: set[tuple[str, str, str]] = set()
    for manifest_file in sorted(rendered_dir.glob("*.yaml")):
        text = manifest_file.read_text()
        for doc in yaml.safe_load_all(text):
            if not doc or not isinstance(doc, dict):
                continue
            api_version = doc.get("apiVersion", "")
            kind = doc.get("kind", "")
            if not kind:
                continue
            group, version = parse_api_version(api_version)
            rendered_gvks.add((kind, group, version))

    skip_kinds = set(settings.kubeconform.skip_kinds)
    uncovered = []
    for kind, group, version in sorted(rendered_gvks):
        if kind in skip_kinds:
            continue
        if group in BUILTIN_API_GROUPS:
            continue
        schema_file = schemas_dir / crd_schema_filename(kind, group, version)
        if not schema_file.exists():
            uncovered.append(f"{kind}/{group}/{version}")

    return uncovered
