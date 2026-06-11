import subprocess

from k8s_validator.config import REPO_ROOT

GENERATOR = (
    REPO_ROOT
    / "gitops"
    / "datastores"
    / "cnpg-eso-verification"
    / "components"
    / "service-database"
    / "generate.py"
)


def validate_service_database_generated_is_current():
    result = subprocess.run(
        ["uv", "run", "--script", str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "service-database generated/ is stale or the generator failed — run "
        "generate.py and commit the result.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
