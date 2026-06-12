from conftest import run_cli_json
from k8s_validator.config import REPO_ROOT


def validate_rendered_manifests_with_conftest(rendered_manifests_dir):
    cmd = [
        "conftest",
        "test",
        "--combine",
        "--namespace",
        "rendered",
        "--policy",
        str(REPO_ROOT / "policies" / "conftest"),
        str(rendered_manifests_dir),
        "--output",
        "json",
    ]

    report = run_cli_json(cmd)
    failures = []
    exceptions = []
    for result in report:
        filename = result.get("filename", "unknown")
        namespace = result.get("namespace", "unknown")
        for failure in result.get("failures", []):
            failures.append(f"  {namespace}:{filename}: {failure.get('msg', '')}")
        for exception in result.get("exceptions", []):
            exceptions.append(f"  {namespace}:{filename}: {exception}")

    assert not failures, "Rendered Conftest violation(s) found:\n" + "\n".join(failures)
    assert not exceptions, "Rendered Conftest exception(s) found:\n" + "\n".join(
        exceptions
    )
