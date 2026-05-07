# LL-0030: `uv sync` defaults to editable installs — multi-stage Docker images that copy only `.venv` break at runtime

## Summary

`uv sync` produces an editable install by default: `.venv/lib/.../site-packages/_editable_impl_<pkg>.pth` references the source tree at the path it lived during build (e.g., `/app/src`). A multi-stage Dockerfile that copies only `.venv` to the runtime stage discards the source tree but preserves the `.pth` pointer to it; the package is technically installed but `import <pkg>` fails at runtime with a `ModuleNotFoundError`. The package metadata survives the copy (so `mypy`/`pytest` in the builder stage see the package and pass), making the failure invisible until a real container actually runs.

## What happened

The convergence-checker's Dockerfile had a builder stage that installed dependencies via `uv sync` and a runtime stage that copied `/app/.venv` and the project's package metadata. CI (linting, type checks, unit tests) ran in the builder stage and passed. The image built. ArgoCD sync passed. Kargo promotions completed. The first time the image actually started in a pod, it crashed with:

```
ModuleNotFoundError: No module named 'convergence_checker'
```

Inspection of `/app/.venv/lib/python3.13/site-packages/` showed `_editable_impl_convergence_checker.pth` containing the path `/app/src` — a path that existed in the builder stage but was deliberately not copied to the runtime stage to keep the image small. The "install" was an editable shim with no source to back it.

## Root cause

`uv sync` defaults to PEP 660 editable installs for the project itself (not for dependencies). The editable install consists of:

- A `.pth` file in `site-packages` pointing back at the project's `src/` directory.
- An import hook that loads modules from that directory at import time.

The metadata files (`<pkg>.dist-info/`) are also placed in `site-packages` and are sufficient for static analysis tools to find the package — so `mypy`, `pytest`, and import-checking linters all succeed in the builder stage. The runtime requires the source directory to actually exist; the dropped `src/` directory in the multi-stage copy is the missing half.

The failure is silent because:

- CI builder smoke tests run inside the builder stage where `/app/src` exists.
- Image build and image push do not exercise import paths.
- ArgoCD sync and Kargo promotion are manifest-shape concerns; they don't run the container.

Detection happens only when the actual pod tries to start.

## Resolution

Build the project as a wheel in the builder stage and install the wheel (non-editable) into the runtime stage:

```dockerfile
# Builder stage
RUN uv build --wheel
# Result: dist/convergence_checker-<version>-py3-none-any.whl

# Runtime stage
COPY --from=builder /app/dist/*.whl /tmp/
RUN uv pip install --system /tmp/convergence_checker-*.whl
```

Alternative resolutions:
- `uv sync --no-editable` in the builder stage.
- `uv pip install --no-deps -e . --no-build-isolation` followed by an explicit wheel build for the runtime stage.

The wheel install is the clean shape: the resulting `site-packages` contains the actual module files, no `.pth` indirection, and the runtime stage no longer depends on a builder-stage path being present.

## How to detect

Symptoms of this class of editable-install runtime failure:

- The image builds successfully; CI passes; the pod immediately crashes with `ModuleNotFoundError` for the project's own package.
- `find /app/.venv -name '_editable_impl_*.pth'` returns matches inside the runtime image.
- The `.pth` file's contents reference a path (e.g., `/app/src`) that does not exist in the runtime stage.

When auditing a Dockerfile for Python projects using `uv`:

- Search for `_editable_impl_*.pth` in the runtime image; any match is a tripwire.
- Verify the runtime stage either contains the source path the `.pth` references, or installs from a wheel.
- Container smoke tests (`docker run <image> python -c "import <pkg>"`) catch this class trivially and should be wired into the build pipeline before the image reaches Kargo promotion. The convergence-checker added one after this incident.
