from __future__ import annotations

from pathlib import Path

from dynaconf import Dynaconf

_SETTINGS_DIR = Path(__file__).resolve().parent.parent.parent

settings = Dynaconf(
    settings_files=[str(_SETTINGS_DIR / "settings.toml")],
    envvar_prefix="CONVERGENCE_CHECKER",
)
