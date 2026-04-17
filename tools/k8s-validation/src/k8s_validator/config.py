import subprocess
import tomllib
from pathlib import Path

from dynaconf import Dynaconf

_SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent


def _get_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def _read_kubectl_version(repo_root: Path) -> str:
    mise_path = repo_root / "mise.toml"
    with open(mise_path, "rb") as f:
        data = tomllib.load(f)
    return data["tools"]["kubectl"]


REPO_ROOT = _get_repo_root()
KUBERNETES_VERSION = _read_kubectl_version(REPO_ROOT)

settings = Dynaconf(settings_files=[str(_SETTINGS_DIR / "settings.yaml")])
