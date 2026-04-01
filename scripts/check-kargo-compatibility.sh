#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

chart_manifest="${repo_root}/gitops/platform/argocd/bootstrap/base/kargo-helm-appset.yaml"
values_file="${repo_root}/gitops/apps/operators/kargo/values.yaml"
mise_file="${repo_root}/mise.toml"
project_config_manifest="${repo_root}/gitops/platform/kargo/project/project-config.yaml"
stage_glob="${repo_root}/gitops/platform/kargo/base/stage-*.yaml"

require_cmd() {
  local cmd="$1"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "ERROR: required command not found: ${cmd}" >&2
    exit 1
  fi
}

require_cmd helm
require_cmd yq
require_cmd rg
require_cmd awk

chart_version="$(
  yq -r '.spec.template.spec.sources[] | select(.chart == "kargo") | .targetRevision' \
    "${chart_manifest}"
)"
if [[ -z "${chart_version}" || "${chart_version}" == "null" ]]; then
  echo "ERROR: failed to read Kargo chart version from ${chart_manifest}" >&2
  exit 1
fi

tool_version="$(awk -F '"' '/"github:akuity\/kargo"/ {print $4; exit}' "${mise_file}")"
if [[ -z "${tool_version}" ]]; then
  echo "ERROR: failed to read github:akuity/kargo tool version from ${mise_file}" >&2
  exit 1
fi

if [[ "${chart_version}" != "${tool_version}" ]]; then
  echo "ERROR: Kargo chart version (${chart_version}) does not match tool version (${tool_version})" >&2
  exit 1
fi

if ! yq -e '.kind == "ProjectConfig"' "${project_config_manifest}" >/dev/null; then
  echo "ERROR: ${project_config_manifest} must define kind: ProjectConfig" >&2
  exit 1
fi

shopt -s nullglob
stage_files=( ${stage_glob} )
if [[ ${#stage_files[@]} -eq 0 ]]; then
  echo "ERROR: no Stage manifests matched ${stage_glob}" >&2
  exit 1
fi

for stage_file in "${stage_files[@]}"; do
  if ! yq -e '.kind == "Stage" and has("spec") and (.spec | has("vars"))' "${stage_file}" >/dev/null; then
    echo "ERROR: ${stage_file} must define Stage.spec.vars" >&2
    exit 1
  fi
done

rendered_chart="$(mktemp)"
trap 'rm -f "${rendered_chart}"' EXIT

helm template kargo oci://ghcr.io/akuity/kargo-charts/kargo \
  --version "${chart_version}" \
  --namespace kargo \
  -f "${values_file}" \
  > "${rendered_chart}"

if ! yq -e 'select(.kind == "CustomResourceDefinition" and .metadata.name == "projectconfigs.kargo.akuity.io")' \
  "${rendered_chart}" >/dev/null; then
  echo "ERROR: rendered chart ${chart_version} does not include CRD projectconfigs.kargo.akuity.io" >&2
  exit 1
fi

if ! yq -e '
  select(.kind == "CustomResourceDefinition" and .metadata.name == "stages.kargo.akuity.io")
  | .spec.versions[]
  | select(.name == "v1alpha1")
  | .schema.openAPIV3Schema.properties.spec.properties
  | has("vars")
' "${rendered_chart}" >/dev/null; then
  echo "ERROR: rendered chart ${chart_version} Stage CRD schema does not include spec.vars" >&2
  exit 1
fi

echo "Kargo compatibility checks passed for chart ${chart_version}."
