from __future__ import annotations

from pathlib import Path

from dynaconf import Dynaconf

_EDITABLE_DEV_SETTINGS = Path(__file__).resolve().parent.parent.parent / "settings.toml"

settings = Dynaconf(
    settings_files=[
        "/app/settings.toml",
        str(_EDITABLE_DEV_SETTINGS),
    ],
    envvar_prefix="CONVERGENCE_CHECKER",
)
