"""
workflows/combat_patrol.py

Combat Patrol workflow.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow

from ._base import (
    GAME_RETRY,
    NAV_RETRY,
    NO_RETRY,
    _cleanup_on_cancel,
    _ControlMixin,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from pydantic import BaseModel

    from activities.combat import engage_enemy, retreat_from_hazard, scan_for_enemy
    from activities.lifecycle import handle_death_respawn


class CombatPatrolParams(BaseModel):
    max_kills: int = 20
    screenshot_every_kills: int = 5


@workflow.defn
class CombatPatrolWorkflow(_ControlMixin):
    """
    Static patrol: stays in place and reacts to enemies entering the field of view.

    Parameters:
        max_kills (int):               Kills before finishing [20]
        screenshot_every_kills (int):  Screenshot every N kills [5]

    get_stats query returns:
        {kills, deaths, escaped, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"kills": 0, "deaths": 0, "escaped": 0, "status": "running"}

    @workflow.run
    async def run(
        self,
        max_kills: int = 20,
        screenshot_every_kills: int = 5,
        _resume_stats: dict | None = None,
    ) -> dict:
        params = CombatPatrolParams(
            max_kills=max_kills,
            screenshot_every_kills=screenshot_every_kills,
        )
        max_kills = params.max_kills
        screenshot_every_kills = params.screenshot_every_kills

        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("CombatPatrolWorkflow started. max_kills=%d", max_kills)

        try:
            return await self._run_patrol(max_kills, screenshot_every_kills)
        except asyncio.CancelledError:
            workflow.logger.warning("CombatPatrolWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("CombatPatrolWorkflow"))
            raise

    async def _run_patrol(self, max_kills: int, screenshot_every_kills: int) -> dict:
        while self._stats["kills"] < max_kills and not self._stop_requested:
            await self._wait_if_paused()
            if self._stop_requested:
                break

            if workflow.info().is_continue_as_new_suggested():
                workflow.logger.info("History getting long — continuing as a new workflow.")
                workflow.continue_as_new(args=[max_kills, screenshot_every_kills, self._stats])

            enemy = await workflow.execute_activity(
                scan_for_enemy,
                schedule_to_close_timeout=timedelta(seconds=25),
                retry_policy=GAME_RETRY,
            )

            if not enemy["found"]:
                await workflow.sleep(timedelta(seconds=1))
                continue

            if enemy["hazard"]:
                workflow.logger.warning(
                    "Hazard enemy '%s' at (%d,%d) — retreating without engaging.", enemy["type"], enemy["x"], enemy["y"]
                )
                await workflow.execute_activity(
                    retreat_from_hazard,
                    schedule_to_close_timeout=timedelta(seconds=25),
                    retry_policy=NO_RETRY,
                )
                await workflow.sleep(timedelta(seconds=10))
                continue

            workflow.logger.info("Enemy '%s' at (%d,%d)", enemy["type"], enemy["x"], enemy["y"])

            result = await workflow.execute_activity(
                engage_enemy,
                args=[enemy["x"], enemy["y"], enemy["type"]],
                schedule_to_close_timeout=timedelta(seconds=90),
                heartbeat_timeout=timedelta(seconds=25),
                retry_policy=NO_RETRY,
            )

            if result == "killed":
                self._stats["kills"] += 1
                kills = self._stats["kills"]
                workflow.logger.info("Kill #%d.", kills)
                if screenshot_every_kills > 0 and kills % screenshot_every_kills == 0:
                    await _screenshot(f"kill_{kills}")

            elif result == "died":
                self._stats["deaths"] += 1
                workflow.logger.warning("Died (death #%d). Respawning...", self._stats["deaths"])
                await workflow.execute_activity(
                    handle_death_respawn,
                    schedule_to_close_timeout=timedelta(seconds=45),
                    retry_policy=NAV_RETRY,
                )
                await workflow.sleep(timedelta(seconds=5))

            elif result == "escaped":
                self._stats["escaped"] += 1
                workflow.logger.info("Fled (low health). Waiting for regeneration.")
                await workflow.sleep(timedelta(seconds=8))

        self._stats["status"] = "stopped"
        await _save_stats("CombatPatrolWorkflow", self._stats)
        return self._stats
