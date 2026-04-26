from __future__ import annotations

import click
import structlog

from convergence_checker.loop import run


@click.command()
@click.option("--dry-run", is_flag=True, help="Log evaluations without reporting to GitHub")
def cli(*, dry_run: bool) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
    )

    run(dry_run=dry_run)
