"""
workflows/afk_session.py

AFK Session workflow coordinating gift farming and combat.
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
    from activities.combat import engage_enemy, retreat_from_hazard, scan_for_enemy
    from activities.inventory import check_inventory_full, collect_doggo_gift
    from activities.lifecycle import handle_death_respawn


@workflow.defn
class AfkSessionWorkflow(_ControlMixin):
    """
    Alternating rotations of gift farming + combat patrol.

    Parameters:
        gift_cycles (int):                  Gift cycles per rotation [10]
        combat_kills_per_rotation (int):    Combat kills per rotation [5]
        total_rotations (int):              Total rotations [20]
        screenshot_every_rotations (int):   Screenshot every N rotations [1]

    get_stats query returns:
        {rotation, total_gifts, total_kills, total_ammo, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "rotation": 0,
            "total_gifts": 0,
            "total_kills": 0,
            "total_ammo": 0,
            "status": "running",
        }

    @workflow.run
    async def run(
        self,
        gift_cycles: int = 10,
        combat_kills_per_rotation: int = 5,
        total_rotations: int = 20,
        screenshot_every_rotations: int = 1,
        _resume_stats: dict | None = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        try:
            return await self._run_session(
                gift_cycles, combat_kills_per_rotation, total_rotations, screenshot_every_rotations
            )
        except asyncio.CancelledError:
            workflow.logger.warning("AfkSessionWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("AfkSessionWorkflow"))
            raise

    async def _run_session(
        self,
        gift_cycles: int,
        combat_kills_per_rotation: int,
        total_rotations: int,
        screenshot_every_rotations: int,
    ) -> dict:
        # On continue-as-new, _stats["rotation"] holds the last started
        # rotation, so a resumed run picks up where the old one left off.
        for rotation in range(self._stats["rotation"], total_rotations):
            if self._stop_requested:
                break
            await self._wait_if_paused()

            if workflow.info().is_continue_as_new_suggested():
                workflow.logger.info("History getting long — continuing as a new workflow.")
                workflow.continue_as_new(
                    args=[
                        gift_cycles,
                        combat_kills_per_rotation,
                        total_rotations,
                        screenshot_every_rotations,
                        self._stats,
                    ]
                )

            self._stats["rotation"] = rotation + 1
            workflow.logger.info(
                "=== Rotation %d/%d | gifts=%d kills=%d ===",
                rotation + 1,
                total_rotations,
                self._stats["total_gifts"],
                self._stats["total_kills"],
            )

            if screenshot_every_rotations > 0 and (rotation + 1) % screenshot_every_rotations == 0:
                await _screenshot(f"rotation_{rotation + 1}")

            # Phase 1: Gift farming
            for _ in range(gift_cycles):
                if self._stop_requested:
                    break
                await self._wait_if_paused()

                gift_result = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=GAME_RETRY,
                )
                if gift_result.get("collected"):
                    self._stats["total_gifts"] += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if inv_full:
                    await _run_craft_cycle(ammo_per_craft=50)
                    self._stats["total_ammo"] += 50

                await workflow.sleep(timedelta(seconds=3))

            # Phase 2: Combat
            kills_this_rotation = 0
            while kills_this_rotation < combat_kills_per_rotation and not self._stop_requested:
                await self._wait_if_paused()

                # The scan loop can spin for hours if no enemies spawn; bail
                # to the rotation boundary where continue-as-new happens.
                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — ending combat phase early.")
                    break

                enemy = await workflow.execute_activity(
                    scan_for_enemy,
                    schedule_to_close_timeout=timedelta(seconds=5),
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
                        schedule_to_close_timeout=timedelta(seconds=10),
                        retry_policy=NO_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=10))
                    continue

                result = await workflow.execute_activity(
                    engage_enemy,
                    args=[enemy["x"], enemy["y"]],
                    schedule_to_close_timeout=timedelta(seconds=30),
                    heartbeat_timeout=timedelta(seconds=5),
                    retry_policy=NO_RETRY,
                )
                if result == "killed":
                    self._stats["total_kills"] += 1
                    kills_this_rotation += 1
                elif result == "died":
                    await workflow.execute_activity(
                        handle_death_respawn,
                        schedule_to_close_timeout=timedelta(seconds=15),
                        retry_policy=NAV_RETRY,
                    )
                    await workflow.sleep(timedelta(seconds=5))

                await workflow.sleep(timedelta(seconds=2))

        self._stats["status"] = "completed"
        await _save_stats("AfkSessionWorkflow", self._stats)
        return self._stats
