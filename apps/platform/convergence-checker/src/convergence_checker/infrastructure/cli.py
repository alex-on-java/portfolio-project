from __future__ import annotations

import sys
from pathlib import Path

import click
import structlog

from convergence_checker.application import ConvergenceChecker, utc_now
from convergence_checker.infrastructure.config import load_settings
from convergence_checker.infrastructure.github import GithubStatusReporter
from convergence_checker.infrastructure.kubernetes import KubernetesGateway


@click.command()
@click.option(
    "--settings",
    "settings_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("settings.toml"),
    show_default=True,
)
def cli(settings_path: Path) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )

    settings = load_settings(settings_path=settings_path)
    cluster = KubernetesGateway.in_cluster(settings.kubernetes)
    reporter = GithubStatusReporter.from_settings(settings.github)
    checker = ConvergenceChecker(
        settings=settings.runtime,
        cluster_reader=cluster,
        write_heartbeat=cluster.write,
        status_reporter=reporter,
        clock=utc_now,
    )
    checker.run_forever()
