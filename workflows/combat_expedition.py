"""
workflows/combat_expedition.py

Full Combat Expedition workflow.
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
    _run_craft_cycle,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from activities.combat import check_ammo_count, engage_enemy, retreat_from_hazard, scan_for_enemy
    from activities.inventory import open_storage_and_deposit_loot
    from activities.lifecycle import handle_death_respawn
    from activities.navigation import navigate_to_location


@workflow.defn
class CombatExpeditionWorkflow(_ControlMixin):
    """
    Full combat expedition:
    1. Checks ammo at the base — crafts more before departing if it's low.
    2. Navigates to 'location' (config.toml [locations.<location>]).
    3. Kills enemies up to max_kills, reusing the same engage_enemy loop
       as CombatPatrolWorkflow (health/fleeing and remains looting are
       already handled there; hazard enemies are avoided, not engaged).
    4. If ammo drops below the minimum mid-expedition, returns to base,
       crafts more, and automatically heads back to the same location.
    5. On reaching max_kills (or receiving 'stop'), returns to base and
       opens a storage container to deposit the loot (shift-click sweep
       of the inventory grid — best-effort, see open_storage_and_deposit_loot).

    Parameters:
        location (str):               Combat location name in [locations.<location>] — required
        max_kills (int):               Kills before ending the expedition [10]
        min_ammo_to_depart (int):      Minimum ammo to leave/continue without resupplying [20]
        ammo_per_craft (int):          Ammo crafted per resupply cycle [50]
        screenshot_every_kills (int):  Screenshot every N kills [5]
        base_location (str):           Return location name in [locations.<name>] ["base"]
        nav_timeout_seconds (int):     Time budget per navigation attempt [45]

    get_stats query returns:
        {kills, deaths, escaped, resupply_trips, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "kills": 0,
            "deaths": 0,
            "escaped": 0,
            "resupply_trips": 0,
            "status": "running",
        }

    @workflow.run
    async def run(
        self,
        location: str,
        max_kills: int = 10,
        min_ammo_to_depart: int = 20,
        ammo_per_craft: int = 50,
        screenshot_every_kills: int = 5,
        base_location: str = "base",
        nav_timeout_seconds: int = 45,
        _resume_stats: dict | None = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        workflow.logger.info("CombatExpeditionWorkflow started. location=%s max_kills=%d", location, max_kills)
        nav_start_to_close = timedelta(seconds=nav_timeout_seconds)
        nav_schedule_to_close = nav_start_to_close * NAV_RETRY.maximum_attempts + timedelta(seconds=20)

        async def _go(target: str) -> None:
            await workflow.execute_activity(
                navigate_to_location,
                args=[target],
                start_to_close_timeout=nav_start_to_close,
                schedule_to_close_timeout=nav_schedule_to_close,
                heartbeat_timeout=timedelta(seconds=25),
                retry_policy=NAV_RETRY,
            )

        async def _ammo() -> int:
            return await workflow.execute_activity(
                check_ammo_count,
                schedule_to_close_timeout=timedelta(seconds=30),
                retry_policy=NO_RETRY,
            )

        try:
            ammo = await _ammo()
            if 0 <= ammo < min_ammo_to_depart:
                workflow.logger.info("Initial ammo is low (%d) — crafting before departing.", ammo)
                await _run_craft_cycle(ammo_per_craft)
                self._stats["resupply_trips"] += 1

            await _go(location)

            while self._stats["kills"] < max_kills and not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — continuing as a new workflow.")
                    workflow.continue_as_new(
                        args=[
                            location,
                            max_kills,
                            min_ammo_to_depart,
                            ammo_per_craft,
                            screenshot_every_kills,
                            base_location,
                            nav_timeout_seconds,
                            self._stats,
                        ]
                    )

                ammo = await _ammo()
                if 0 <= ammo < min_ammo_to_depart:
                    workflow.logger.warning("Low ammo (%d) — heading back to resupply.", ammo)
                    self._stats["resupply_trips"] += 1
                    await _go(base_location)
                    await _run_craft_cycle(ammo_per_craft)
                    await _go(location)
                    continue

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
                        "Hazard enemy '%s' at (%d,%d) — retreating without engaging.",
                        enemy["type"],
                        enemy["x"],
                        enemy["y"],
                    )
                    await workflow.execute_activity(
                        retreat_from_hazard,
                        schedule_to_close_timeout=timedelta(seconds=25),
                        retry_policy=NO_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=10))
                    continue

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
                    workflow.logger.info("Kill #%d/%d.", kills, max_kills)
                    if screenshot_every_kills > 0 and kills % screenshot_every_kills == 0:
                        await _screenshot(f"expedition_kill_{kills}")
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

            workflow.logger.info("Expedition complete — heading back to base.")
            await _go(base_location)
            await workflow.execute_activity(
                open_storage_and_deposit_loot,
                start_to_close_timeout=timedelta(seconds=60),
                schedule_to_close_timeout=timedelta(seconds=120),
                retry_policy=GAME_RETRY,
            )

            self._stats["status"] = "completed"
            await _save_stats("CombatExpeditionWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("CombatExpeditionWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("CombatExpeditionWorkflow"))
            raise
