from conftest import run_cli_json


def validate_schemas_with_kubeconform(kubeconform_settings, rendered_manifests_dir):
    cmd = ["kubeconform", "-summary", "-output", "json", "-strict"]

    cmd.extend(["-kubernetes-version", kubeconform_settings["kubernetes_version"]])

    for loc in kubeconform_settings["schema_locations"]:
        cmd.extend(["-schema-location", loc])

    for kind in kubeconform_settings["skip_kinds"]:
        cmd.extend(["-skip", kind])

    cmd.append(str(rendered_manifests_dir))

    report = run_cli_json(cmd)
    summary = report["summary"]

    problems = []
    for res in report.get("resources", []):
        status = res.get("status", "")
        if status in ("statusInvalid", "statusError"):
            name = res.get("name", "unknown")
            kind = res.get("kind", "unknown")
            msg = res.get("msg", "")
            problems.append(f"  [{status}] {kind}/{name}: {msg}")

    detail = ""
    if summary["invalid"] > 0 or summary["errors"] > 0:
        detail = (
            f"Kubeconform: {summary['invalid']} invalid, "
            f"{summary['errors']} errors\n" + "\n".join(problems)
        )

    assert summary["invalid"] == 0, detail
    assert summary["errors"] == 0, detail
