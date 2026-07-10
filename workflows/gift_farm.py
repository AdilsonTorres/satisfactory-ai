"""
workflows/gift_farm.py

AFK Gift Farm workflow — multi-doggo.
"""

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from ._base import (
    GAME_RETRY,
    PERSIST_TASK_QUEUE,
    _cleanup_on_cancel,
    _ControlMixin,
    _run_craft_cycle,
    _save_stats,
    _screenshot,
)

with workflow.unsafe.imports_passed_through():
    from activities.inventory import check_inventory_full, collect_doggo_gift
    from activities.records import record_gift_check


@workflow.defn
class GiftFarmWorkflow(_ControlMixin):
    """
    AFK farming loop over a roster of named Lizard Doggos.

    Parameters:
        doggos (list[dict]):            Roster from config [[taming.doggos]]:
            [{name, turn_dx}, ...] checked in order each cycle. turn_dx is
            the relative yaw from the previous doggo (list wraps — see
            config.toml). Defaults to a single anonymous doggo.
        ammo_per_craft (int):           Rifle Ammo per craft cycle [50]
        screenshot_every_cycles (int):  Screenshot every N cycles [10]
        cycle_interval_seconds (float): Sleep between cycles [75.0]. The
            gift roll only starts once a doggo's one-slot inventory is
            empty and averaged ~15min measured live with one doggo, so
            short intervals are mostly menu/camera churn. Reverted from
            50s to 75s on 2026-07-08 to reduce camera/menu churn.
            (written via record_gift_check) has the data to compare.

    Every check — hit or empty — is persisted per doggo with timestamp,
    OCR'd item name and slot diff, so time-between-gifts and items/hour
    can be analyzed later.

    get_stats query returns:
        {gifts, ammo_crafted, cycles, gifts_by_doggo, items, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "gifts": 0,
            "ammo_crafted": 0,
            "cycles": 0,
            "gifts_by_doggo": {},
            "items": {},
            "status": "running",
        }

    async def _check_any_doggo(self, unchecked_doggos: list[dict]) -> dict:
        try:
            result = await workflow.execute_activity(
                collect_doggo_gift,
                args=[unchecked_doggos],
                schedule_to_close_timeout=timedelta(seconds=90),
                retry_policy=GAME_RETRY,
            )
        except Exception as exc:
            # The host game worker can be transiently offline (not started
            # yet at the scheduled hour, machine rebooted, etc.) — measured
            # live 2026-07-05: with it down, this activity exhausts its
            # retry budget and an UNCAUGHT failure took the whole workflow
            # down with it, losing an unattended run and its stats. Skip
            # this cycle instead; the next cycle just retries.
            workflow.logger.warning(
                "collect_doggo_gift failed (host game worker offline?): %s",
                exc,
            )
            return {}
        collected = bool(result.get("collected"))
        name = result.get("doggo") or "unknown"
        if collected:
            self._stats["gifts"] += 1
            self._stats["gifts_by_doggo"][name] = self._stats["gifts_by_doggo"].get(name, 0) + 1
            item = result.get("item") or "unknown"
            self._stats["items"][item] = self._stats["items"].get(item, 0) + 1

        # Persist the observation (found OR empty) for interval analysis.
        # Never let a bookkeeping hiccup kill the farm loop.
        try:
            await workflow.execute_activity(
                record_gift_check,
                args=[result],
                task_queue=PERSIST_TASK_QUEUE,
                schedule_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        except Exception as exc:
            workflow.logger.warning("record_gift_check failed (continuing): %s", exc)
        return result

    @workflow.run
    async def run(
        self,
        doggos: list[dict] | None = None,
        ammo_per_craft: int = 50,
        screenshot_every_cycles: int = 10,
        cycle_interval_seconds: float = 75.0,
        _resume_stats: dict | None = None,
    ) -> dict:
        if _resume_stats is not None:
            self._stats = _resume_stats
        roster = doggos or [{"name": "doggo", "turn_dx": 0}]
        workflow.logger.info("GiftFarmWorkflow started. Roster: %s", ", ".join(d["name"] for d in roster))

        try:
            while not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                if workflow.info().is_continue_as_new_suggested():
                    workflow.logger.info("History getting long — continuing as a new workflow.")
                    workflow.continue_as_new(
                        args=[
                            roster,
                            ammo_per_craft,
                            screenshot_every_cycles,
                            cycle_interval_seconds,
                            self._stats,
                        ]
                    )

                self._stats["cycles"] += 1
                cycle = self._stats["cycles"]
                cycle_started = workflow.now()
                workflow.logger.info(
                    "Cycle #%d | gifts=%d ammo=%d", cycle, self._stats["gifts"], self._stats["ammo_crafted"]
                )

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"gift_cycle_{cycle}")

                collected_any = False
                unchecked = list(roster)
                while unchecked and not self._stop_requested:
                    result = await self._check_any_doggo(unchecked)
                    processed_name = result.get("doggo")
                    if processed_name:
                        # Remove the processed doggo from unchecked list
                        matching = [d for d in unchecked if d["name"] == processed_name]
                        if matching:
                            unchecked.remove(matching[0])
                        else:
                            # Fuzzy matching fallback
                            matching_fuzzy = [
                                d
                                for d in unchecked
                                if processed_name.strip().lower().startswith(d["name"].strip().lower())
                            ]
                            if matching_fuzzy:
                                unchecked.remove(matching_fuzzy[0])
                            else:
                                unchecked.pop(0)
                        collected_any = collected_any or bool(result.get("collected"))
                    else:
                        break

                # The player inventory only fills through collected gifts, so
                # the (menu-churny) fullness check is pointless on empty
                # cycles — measured live 2026-07-04: ~90% of cycles.
                if collected_any:
                    try:
                        inv_full = await workflow.execute_activity(
                            check_inventory_full,
                            schedule_to_close_timeout=timedelta(seconds=30),
                            retry_policy=GAME_RETRY,
                        )
                        if inv_full:
                            await _screenshot(f"inv_full_{cycle}")
                            await _run_craft_cycle(ammo_per_craft)
                            self._stats["ammo_crafted"] += ammo_per_craft
                    except Exception as exc:
                        workflow.logger.warning("Inventory check/craft failed (continuing): %s", exc)

                # Deadline-based: interval is the CADENCE, not an extra sleep
                # on top of the ~15-30s the checks themselves take (which had
                # stretched the real cycle to ~100s at interval=60).
                elapsed = (workflow.now() - cycle_started).total_seconds()
                await workflow.sleep(timedelta(seconds=max(5.0, cycle_interval_seconds - elapsed)))

            self._stats["status"] = "stopped"
            await _save_stats("GiftFarmWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("GiftFarmWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("GiftFarmWorkflow"))
            raise
