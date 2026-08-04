"""
workflows/depot_coal.py

Depot Coal → Storage transfer workflow.
"""

import asyncio
from datetime import timedelta
from typing import Any

from temporalio import workflow

from ._base import (
    GAME_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _save_stats,
)

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities import deposit_coal_to_storage, download_coal_from_depot


class DepotCoalParams(BaseModel):
    interval_seconds: float = 15.0
    max_cycles: int | None = None
    stacks_per_cycle: int = 5


@workflow.defn
class DepotCoalToStorageWorkflow(_ControlMixin):
    """
    Periodically pulls Coal from a depot inventory and deposits it into
    storage. Runs indefinitely until a 'stop' signal is received or
    max_cycles is reached.

    Parameters:
        interval_seconds (float):  Sleep between cycles [15.0]
        max_cycles (int | None):   Stop after N cycles; None = run forever [None]
        stacks_per_cycle (int):    Coal stacks to pull per cycle [5]

    get_stats query returns:
        {cycles, stacks_transferred, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"cycles": 0, "stacks_transferred": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        interval_seconds: float = 15.0,
        max_cycles: int | None = None,
        stacks_per_cycle: int = 5,
        _resume_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = DepotCoalParams(
            interval_seconds=interval_seconds,
            max_cycles=max_cycles,
            stacks_per_cycle=stacks_per_cycle,
        )
        interval_seconds = params.interval_seconds
        max_cycles = params.max_cycles
        stacks_per_cycle = params.stacks_per_cycle

        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("DepotCoalToStorageWorkflow started.")

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                if max_cycles is not None and self._stats["cycles"] >= max_cycles:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — continuing as a new workflow.")
                    workflow.continue_as_new(args=[interval_seconds, max_cycles, stacks_per_cycle, self._stats])

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]
                workflow.logger.info("Cycle #%d starting.", cycle)

                # Step 1: Download Coal from depot
                try:
                    await workflow.execute_activity(
                        download_coal_from_depot,
                        args=[stacks_per_cycle],
                        schedule_to_close_timeout=timedelta(seconds=60),
                        retry_policy=GAME_RETRY,
                    )
                except Exception as exc:
                    workflow.logger.error("download_coal_from_depot failed: %s", exc)
                    await workflow.sleep(timedelta(seconds=interval_seconds))
                    continue

                # Step 2: Deposit Coal to storage
                deposited = 0
                try:
                    deposited = await workflow.execute_activity(
                        deposit_coal_to_storage,
                        schedule_to_close_timeout=timedelta(seconds=60),
                        retry_policy=GAME_RETRY,
                    )
                    self._stats["stacks_transferred"] += deposited
                except Exception as exc:
                    workflow.logger.error("deposit_coal_to_storage failed: %s", exc)

                workflow.logger.info(
                    "Cycle #%d finished. Deposited stacks: %d (total: %d)",
                    cycle,
                    deposited,
                    self._stats["stacks_transferred"],
                )

                await workflow.sleep(timedelta(seconds=interval_seconds))

            self._stats["status"] = "stopped"
            await _save_stats("DepotCoalToStorageWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("DepotCoalToStorageWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("DepotCoalToStorageWorkflow"))
            raise
