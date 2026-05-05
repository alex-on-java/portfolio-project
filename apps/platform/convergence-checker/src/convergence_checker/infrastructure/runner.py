from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from convergence_checker.core import cycle
from convergence_checker.core.models import CycleInputs

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from convergence_checker.core.cycle import CycleConfig
    from convergence_checker.core.ports import ClusterReader, StatusReporter

log: structlog.stdlib.BoundLogger = structlog.get_logger()


@dataclass(frozen=True)
class LoopPacing:
    sleep: Callable[[float], None]
    clock: Callable[[], datetime]
    should_continue: Callable[[], bool]
    interval_seconds: float


def run_until(
    *,
    initial_inputs: CycleInputs,
    reader: ClusterReader,
    reporter: StatusReporter,
    config: CycleConfig,
    pacing: LoopPacing,
) -> None:
    inputs = initial_inputs
    while pacing.should_continue():
        outputs = cycle.run_cycle(inputs, reader, reporter, config, now=pacing.clock())
        log.info(
            "evaluation",
            verdict=outputs.result.verdict.value,
            description=outputs.result.description,
            consecutive_healthy=outputs.new_state.consecutive_healthy,
            resources=outputs.resource_count,
        )
        inputs = CycleInputs(
            previous_state=outputs.new_state,
            previous_commit=outputs.new_commit,
            previous_sent_status=outputs.new_sent_status,
        )

        pacing.sleep(pacing.interval_seconds)
