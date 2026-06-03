from pathlib import Path

import yaml

SENTINEL_REMOTE_REF_KEY = "REPLACE_IN_OVERLAY"
PRODUCTION_KEY_SUFFIX = "-prd"

# Renders are named "kustomize--<sanitized-overlay-path>.yaml" by
# rendering.py, with path separators and dots collapsed to "-".
OVERLAYS_PATH_MARKER = "overlays"
MAIN_LIFECYCLE_SEGMENT = "main"

EXPECTED_REMOTE_KEYS = {
    ("any", "dev"): "portfolio-project-web-app-demo-dev",
    ("any", "stg"): "portfolio-project-web-app-demo-stg",
    ("ephemeral", "prd"): "portfolio-project-web-app-demo-stg",
    ("main", "prd"): "portfolio-project-web-app-demo-prd",
}


def _overlay_segments(render: Path) -> tuple[str, ...]:
    tokens = render.stem.split("-")
    try:
        idx = tokens.index(OVERLAYS_PATH_MARKER)
    except ValueError:
        return ()
    return tuple(tokens[idx + 1 :])


def _is_ephemeral_reachable(render: Path) -> bool:
    segments = _overlay_segments(render)
    if not segments:
        return False
    return segments[0] != MAIN_LIFECYCLE_SEGMENT


def _external_secret_remote_keys(doc: dict) -> list[str]:
    keys: list[str] = []
    spec = doc.get("spec", {})
    for entry in spec.get("data", []):
        remote_ref = entry.get("remoteRef", {})
        key = remote_ref.get("key")
        if key is not None:
            keys.append(key)
    for entry in spec.get("dataFrom", []):
        extract = entry.get("extract", {})
        key = extract.get("key")
        if key is not None:
            keys.append(key)
    return keys


def _external_secret_has_find(doc: dict) -> bool:
    # A dataFrom.find match set resolves at reconcile time and cannot be
    # enumerated from the rendered manifest, so its keys cannot be checked
    # against the production suffix statically.
    spec = doc.get("spec", {})
    return any("find" in entry for entry in spec.get("dataFrom", []))


def _iter_external_secrets(render: Path):
    text = render.read_text(encoding="utf-8")
    for doc in yaml.safe_load_all(text):
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") != "ExternalSecret":
            continue
        name = doc.get("metadata", {}).get("name", "unknown")
        yield name, _external_secret_remote_keys(doc), _external_secret_has_find(doc)


def validate_no_sentinel_in_rendered_secrets(rendered_manifests_dir):
    offenders = []
    for render in sorted(Path(rendered_manifests_dir).glob("kustomize--*.yaml")):
        for name, keys, _has_find in _iter_external_secrets(render):
            for key in keys:
                if key == SENTINEL_REMOTE_REF_KEY:
                    offenders.append(
                        f"  {render.name}: ExternalSecret/{name} remoteRef.key={key}"
                    )

    assert not offenders, (
        f"Unreplaced base sentinel '{SENTINEL_REMOTE_REF_KEY}' found in rendered "
        "ExternalSecret(s). Every environment overlay must patch remoteRef.key "
        "to a real GSM key:\n" + "\n".join(offenders)
    )


def validate_no_production_key_in_ephemeral(rendered_manifests_dir):
    offenders = []
    for render in sorted(Path(rendered_manifests_dir).glob("kustomize--*.yaml")):
        if not _is_ephemeral_reachable(render):
            continue
        for name, keys, has_find in _iter_external_secrets(render):
            for key in keys:
                if key.endswith(PRODUCTION_KEY_SUFFIX):
                    offenders.append(
                        f"  {render.name}: ExternalSecret/{name} remoteRef.key={key}"
                    )
            if has_find:
                offenders.append(
                    f"  {render.name}: ExternalSecret/{name} spec.dataFrom[].find"
                )

    assert not offenders, (
        "Ephemeral production-like overlay references a production GSM key "
        f"(suffix '{PRODUCTION_KEY_SUFFIX}') or uses a dataFrom.find pattern whose "
        "match set cannot be statically verified. Temporary environments must not "
        "consume real production Tier A material:\n" + "\n".join(offenders)
    )


def validate_expected_remote_keys(rendered_manifests_dir):
    offenders = []
    seen = set()
    for render in sorted(Path(rendered_manifests_dir).glob("kustomize--*.yaml")):
        segments = _overlay_segments(render)
        if len(segments) < 2:
            continue
        env_key = (segments[0], segments[1])
        expected = EXPECTED_REMOTE_KEYS.get(env_key)
        if expected is None:
            continue
        seen.add(env_key)
        rendered_keys = []
        uses_find = False
        for _name, keys, has_find in _iter_external_secrets(render):
            rendered_keys.extend(keys)
            uses_find = uses_find or has_find
        if uses_find:
            offenders.append(
                f"  {render.name}: an ExternalSecret uses dataFrom[].find; "
                f"expected an explicit remoteRef.key={expected}"
            )
        elif expected not in rendered_keys:
            offenders.append(
                f"  {render.name}: GSM remoteRef.key(s)={rendered_keys or '[]'}; "
                f"expected {expected}"
            )

    missing = sorted(set(EXPECTED_REMOTE_KEYS) - seen)
    for env_key in missing:
        offenders.append(
            f"  overlays/{env_key[0]}/{env_key[1]}: no render found; expected an "
            f"ExternalSecret with remoteRef.key={EXPECTED_REMOTE_KEYS[env_key]}"
        )

    assert not offenders, (
        "Rendered overlay does not map to its expected GSM key. The lifecycle "
        "key mapping (any/dev->dev, any/stg->stg, ephemeral/prd->stg, "
        "main/prd->prd) must hold so a copy-paste regression cannot silently "
        "swap an environment's production key:\n" + "\n".join(offenders)
    )
