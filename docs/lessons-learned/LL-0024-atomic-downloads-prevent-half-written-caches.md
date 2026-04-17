# LL-0024: Atomic downloads prevent half-written schema caches from corrupting subsequent runs

## Summary

`urllib.request.urlretrieve` writes directly to the target path and leaves a truncated file on disk if the process is interrupted (Ctrl-C, crash, signal). Subsequent runs treat the half-written file as a valid cache entry and fail downstream with cryptic errors. A stream + temp-file + `os.replace` pattern, guarded by a `BaseException` cleanup, makes downloads atomic and interrupt-safe.

## What happened

During development of the schema-download pipeline, a Ctrl-C during a long `generate-schemas` run left one schema file on disk at partial size. The next run picked that file up as valid, fed it to `kubeconform`, and produced a misleading "invalid schema" error several layers away from the real cause. Tracing the original interrupt took more time than the interrupt itself had saved.

## Root cause

`urllib.request.urlretrieve(url, dest)` opens `dest` for writing and streams bytes into it in-place. If the process dies mid-download, the partial file remains at its final path with no indication that it is incomplete. Subsequent runs have no way to distinguish a partial file from a valid one — filesystems don't carry "download-in-progress" metadata, and the content can be syntactically valid JSON even when truncated.

## Resolution

Replaced `urlretrieve` in `tools/k8s-validation/src/k8s_validator/schemas.py` with a module-private `_download_atomic(url, dest)`:

1. Open the response via `urllib.request.urlopen(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)` (10 s per-socket-operation, sufficient for KB-scale schema files).
2. Stream bytes via `shutil.copyfileobj(response, fh)` into `<dest>.tmp`.
3. On successful completion, `os.replace(tmp, dest)` atomically swaps the temp file into place.
4. Wrap steps 1–3 in `try/except BaseException` — *not* `Exception` — so `KeyboardInterrupt` and `SystemExit` also trigger `.tmp` cleanup before re-raising.

`os.replace` is atomic on same-filesystem paths. The `.tmp` sibling stays inside the cache directory, so the atomicity guarantee holds.

## How to detect

If a download-and-cache pipeline fails downstream with "invalid content" errors after an earlier aborted run, inspect the cache directory for:

- Files whose size is suspiciously small relative to the expected payload.
- Files whose trailing bytes are truncated (JSON missing a closing brace, YAML missing a document end).
- Files modified around the timestamp of the previous aborted run.

Any download-into-cache path should use the temp-file + atomic-rename pattern, with cleanup keyed on `BaseException` rather than `Exception` — `KeyboardInterrupt` inherits from `BaseException`, not `Exception`, and will bypass cleanup that only catches the latter.
