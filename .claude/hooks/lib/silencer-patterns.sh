# shellcheck shell=bash

silencer_hash_pattern() {
  echo '#[[:space:]]*(noqa|pylint:[[:space:]]*disable|pyright:[[:space:]]*ignore|type:[[:space:]]*ignore|mypy:[[:space:]]*ignore|ruff:[[:space:]]*noqa|fmt:[[:space:]]*(off|on|skip)|pragma:[[:space:]]*no[[:space:]]+cover|shellcheck[[:space:]]+disable|yamllint[[:space:]]+disable|tflint-ignore|checkov:skip)'
}

silencer_slash_pattern() {
  echo '//[[:space:]]*(eslint-(disable|disable-line|disable-next-line)|@ts-(ignore|expect-error|nocheck)|biome-ignore|prettier-ignore|noinspection|NOSONAR|NOPMD|SuppressWarnings)'
}

silencer_block_pattern() {
  echo '\*[[:space:]]*(eslint-disable|biome-ignore|prettier-ignore|istanbul[[:space:]]+ignore|c8[[:space:]]+ignore)'
}

silencer_annotation_pattern() {
  echo '(^|[[:space:]])@(SuppressWarnings|Suppress|SuppressLint|SuppressFBWarnings)[[:space:]]*\('
}
