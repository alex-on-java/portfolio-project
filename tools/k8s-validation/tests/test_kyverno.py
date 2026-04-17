from conftest import run_cli_json


def test_kyverno_resource_policies(kyverno_policies_dir, rendered_manifests_dir):
    cmd = [
        "kyverno",
        "apply",
        str(kyverno_policies_dir),
        "--resource",
        str(rendered_manifests_dir),
        "-p",
        "--output-format",
        "json",
    ]

    report = run_cli_json(cmd)
    summary = report["summary"]
    failures = [r for r in report["results"] if r["result"] == "fail"]

    if failures:
        lines = [f"Kyverno: {summary['fail']} violation(s) found:\n"]
        for f in failures:
            res = f["resources"][0]
            lines.append(
                f"  {res['kind']}/{res.get('namespace', '')}/{res['name']}: "
                f"{f['message']}"
            )
        detail = "\n".join(lines)
    else:
        detail = ""

    assert summary["fail"] == 0, detail
    assert summary["error"] == 0, (
        f"Kyverno: {summary['error']} policy evaluation error(s)"
    )
