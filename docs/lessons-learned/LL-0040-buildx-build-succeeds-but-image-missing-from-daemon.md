# LL-0040: Default `docker/setup-buildx-action` Driver Needs `--load` for a Separate `docker push` to Find the Image

## Summary

`docker/setup-buildx-action` provisions the `docker-container` driver by default. Under that driver, `docker buildx build` writes the result into the internal BuildKit cache only; no image lands in the local docker daemon. A subsequent `docker push` step then fails with `An image does not exist locally with the tag: ghcr.io/...`. Buildx prints the fix verbatim during the build, but the error surfaces in a different step, so the warning is easy to miss when triaging the publish failure.

## What Happened

The `build-image` target invoked `docker buildx build` without `--load`. That build step succeeded, with one warning line in the log:

```
WARNING: No output specified with docker-container driver. Build result
will only remain in the build cache. To push result image into registry
use --push or to load image into docker use --load
```

The dependent `publish-image` step then ran `docker push ghcr.io/.../<sha>` against an empty daemon and failed:

```
An image does not exist locally with the tag: ghcr.io/alex-on-java/web-app:<sha>
```

Triage focused on `publish-image` first, since that was the step that surfaced the failure. The relevant warning sat a few hundred log lines upstream, in a different job step entirely.

## Root Cause

`docker buildx build` honours the driver of the active builder. By default, `docker/setup-buildx-action` provisions a builder that uses the `docker-container` driver, which runs BuildKit inside a container and writes outputs to the cache of that container. The local docker daemon is a separate scope; BuildKit does not push into it implicitly. Three explicit output modes exist:

- `--load`: copy the result into the local docker daemon. A separate `docker push` then finds it.
- `--push`: push the result directly to the registry from BuildKit. The local daemon never sees it.
- (no flag): keep the result in the internal BuildKit cache only. Useful for cache-warming jobs; useless for any subsequent step that expects a local image.

The trap is silent because the no-flag mode is not an error. By the definition of BuildKit the build "succeeds": the warning emits once, and any downstream step reasoning in terms of the docker daemon discovers the gap.

## Resolution

Add `--load` to `build-image`. Both the `web-app` and `convergence-checker` `project.json` files now invoke:

```
docker buildx build --load --tag ghcr.io/alex-on-java/<app>:${IMAGE_TAG:-$(git rev-parse HEAD)} ${BUILDX_CACHE_ARGS:-} {projectRoot}
```

`--load` was preferred over `--push` per [ADR-026](../architecture/decision-records/ADR-026-image-build-ci-strategy.md). The build/publish split keeps build failures and registry-auth failures attributable to separate CI steps; fusing them via `--push` would lose that. Switching the builder driver to `docker` was rejected because it removes the GHA layer cache and multi-platform support that `docker-container` provides.

## How to Detect

Symptoms of this class of buildx-driver/daemon mismatch:

- A `docker push` step fails with `An image does not exist locally with the tag: ...` immediately after a `docker buildx build` step that reported success.
- The log of the build step contains `WARNING: No output specified with docker-container driver`.
- `docker images` after the build shows no entry for the tag the build claimed to produce.

Adoption rule: when a workflow uses `docker/setup-buildx-action` together with a separate `docker push` step (the build/publish split pattern), the `docker buildx build` invocation must include `--load`. The implicit `docker-container` driver default is the trap; the `--load` flag closes it. If build and publish are deliberately fused into one step, `--push` is the right shape and a separate `docker push` step is redundant.
