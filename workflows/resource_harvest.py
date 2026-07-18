"""
workflows/resource_harvest.py

Manual Resource Harvesting workflow.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow

from ._base import (
    GAME_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities.crafting import harvest_resource_node


class ResourceHarvestParams(BaseModel):
    swings_per_cycle: int = 20
    cycles: int = 0
    screenshot_every_cycles: int = 10


@workflow.defn
class ResourceHarvestWorkflow(_ControlMixin):
    """
    Manual harvesting loop at a fixed resource node. The player needs to
    be positioned within the node's interaction range before triggering
    the workflow — there's no navigation/pathfinding to the node.

    Parameters:
        swings_per_cycle (int):        Interactions per cycle [20]
        cycles (int):                  0 = infinite until 'stop', N = ends after N cycles [0]
        screenshot_every_cycles (int): Screenshot every N cycles [10]

    get_stats query returns:
        {cycles, total_swings, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"cycles": 0, "total_swings": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        swings_per_cycle: int = 20,
        cycles: int = 0,
        screenshot_every_cycles: int = 10,
        _resume_stats: dict | None = None,
    ) -> dict:
        params = ResourceHarvestParams(
            swings_per_cycle=swings_per_cycle,
            cycles=cycles,
            screenshot_every_cycles=screenshot_every_cycles,
        )
        swings_per_cycle = params.swings_per_cycle
        cycles = params.cycles
        screenshot_every_cycles = params.screenshot_every_cycles

        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("ResourceHarvestWorkflow started. swings_per_cycle=%d", swings_per_cycle)

        # Timeout budget sized off swings_per_cycle itself, so it tracks
        # the activity's real runtime instead of using a fixed value.
        per_attempt = timedelta(seconds=swings_per_cycle * 1.5 + 10)
        schedule_to_close = per_attempt * GAME_RETRY.maximum_attempts + timedelta(seconds=10)

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break
                if cycles > 0 and self._stats["cycles"] >= cycles:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — continuing as a new workflow.")
                    workflow.continue_as_new(args=[swings_per_cycle, cycles, screenshot_every_cycles, self._stats])

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"harvest_cycle_{cycle}")

                swings = await workflow.execute_activity(
                    harvest_resource_node,
                    args=[swings_per_cycle],
                    start_to_close_timeout=per_attempt,
                    schedule_to_close_timeout=schedule_to_close,
                    heartbeat_timeout=timedelta(seconds=8),
                    retry_policy=GAME_RETRY,
                )
                self._stats["total_swings"] += swings

                await workflow.sleep(timedelta(seconds=2))

            self._stats["status"] = "stopped"
            await _save_stats("ResourceHarvestWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("ResourceHarvestWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("ResourceHarvestWorkflow"))
            raise
