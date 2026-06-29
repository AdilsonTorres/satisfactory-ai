"""
workflows/gift_farm.py

AFK Gift Farm workflow.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow

from ._base import (
    GAME_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _run_craft_cycle,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from activities.inventory import check_inventory_full, collect_doggo_gift


@workflow.defn
class GiftFarmWorkflow(_ControlMixin):
    """
    AFK farming loop for Lizard Doggo gifts.

    Parameters:
        ammo_per_craft (int):           Rifle Ammo per craft cycle [50]
        screenshot_every_cycles (int):  Screenshot every N cycles [10]

    get_stats query returns:
        {gifts, ammo_crafted, cycles, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"gifts": 0, "ammo_crafted": 0, "cycles": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        ammo_per_craft: int = 50,
        screenshot_every_cycles: int = 10,
        _resume_stats: dict | None = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("GiftFarmWorkflow started.")

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — continuing as a new workflow.")
                    workflow.continue_as_new(args=[ammo_per_craft, screenshot_every_cycles, self._stats])

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]
                workflow.logger.info(
                    "Cycle #%d | gifts=%d ammo=%d", cycle, self._stats["gifts"], self._stats["ammo_crafted"]
                )

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"gift_cycle_{cycle}")

                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=60),
                    retry_policy=GAME_RETRY,
                )
                if collected:
                    self._stats["gifts"] += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=GAME_RETRY,
                )
                if inv_full:
                    await _screenshot(f"inv_full_{cycle}")
                    await _run_craft_cycle(ammo_per_craft)
                    self._stats["ammo_crafted"] += ammo_per_craft

                await workflow.sleep(timedelta(seconds=3))

            self._stats["status"] = "stopped"
            await _save_stats("GiftFarmWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("GiftFarmWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("GiftFarmWorkflow"))
            raise
