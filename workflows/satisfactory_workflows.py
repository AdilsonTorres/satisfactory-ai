"""
workflows/satisfactory_workflows.py

Workflows with:
- Signals: pause / resume / stop
- Queries: get_stats
- Configurable periodic screenshots
- Stats persisted to JSON at the end (via the persist_session_stats activity)

CLI control:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""
import asyncio
import logging
import math
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.game_activities import (
        collect_doggo_gift,
        check_inventory_full,
        check_health_low,
        feed_wild_doggo,
        navigate_to_equipment_workshop,
        craft_rifle_ammo,
        navigate_back_to_base,
        harvest_resource_node,
        scan_for_enemy,
        engage_enemy,
        retreat_from_hazard,
        handle_death_respawn,
        take_debug_screenshot,
        persist_session_stats,
        capture_template_screen,
        extract_templates_from_screen,
        verify_matching_templates,
        reset_to_safe_state,
        navigate_to_location,
        check_ammo_count,
        open_storage_and_deposit_loot,
        get_exploration_route,
        capture_base_reference,
        explore_leg,
        return_via_reverse_route,
    )

logger = logging.getLogger(__name__)

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
    # FileNotFoundError = missing template = a bug, not a retry
    # NavigationError after max_attempts = aborts the workflow
    non_retryable_error_types=["FileNotFoundError"],
)

NAV_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=5,
    backoff_coefficient=1.5,
)

NO_RETRY = RetryPolicy(maximum_attempts=1)

_SS_TIMEOUT = timedelta(seconds=10)
_SS_RETRY   = RetryPolicy(maximum_attempts=1)


async def _screenshot(label: str) -> None:
    await workflow.execute_activity(
        take_debug_screenshot,
        args=[label],
        schedule_to_close_timeout=_SS_TIMEOUT,
        retry_policy=_SS_RETRY,
    )


async def _save_stats(workflow_type: str, stats: dict) -> None:
    await workflow.execute_activity(
        persist_session_stats,
        args=[workflow_type, stats],
        schedule_to_close_timeout=timedelta(seconds=15),
        retry_policy=RetryPolicy(maximum_attempts=2),
    )


async def _cleanup_on_cancel(workflow_type: str) -> None:
    """Closes any open menus in the game before letting the cancellation exception propagate."""
    try:
        await workflow.execute_activity(
            reset_to_safe_state,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
    except Exception as exc:
        workflow.logger.error("Cancellation cleanup for %s failed: %s", workflow_type, exc)


# NAV_RETRY allows 5 attempts with backoff (2s, 3s, 4.5s, 6.75s ~= 16.25s of waiting).
# schedule_to_close_timeout needs to cover that backoff plus the execution time of
# every attempt, not just one — that's why it's larger than start_to_close_timeout.
async def _run_craft_cycle(ammo_per_craft: int) -> None:
    await workflow.execute_activity(
        navigate_to_equipment_workshop,
        start_to_close_timeout=timedelta(seconds=10),
        schedule_to_close_timeout=timedelta(seconds=70),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=NAV_RETRY,
    )
    await workflow.execute_activity(
        craft_rifle_ammo,
        args=[ammo_per_craft],
        start_to_close_timeout=timedelta(seconds=15),
        schedule_to_close_timeout=timedelta(seconds=60),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=GAME_RETRY,
    )
    await workflow.execute_activity(
        navigate_back_to_base,
        start_to_close_timeout=timedelta(seconds=8),
        schedule_to_close_timeout=timedelta(seconds=60),
        retry_policy=NAV_RETRY,
    )


# ---------------------------------------------------------------------------
# Control mixin (pause / resume / stop / get_stats)
# ---------------------------------------------------------------------------

class _ControlMixin:
    """Signals and query shared by all workflows."""

    def __init__(self) -> None:
        self._paused = False
        self._stop_requested = False
        self._stats: dict = {"status": "running"}

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True
        self._stats["status"] = "paused"
        workflow.logger.info("Paused.")

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self._stats["status"] = "running"
        workflow.logger.info("Resumed.")

    @workflow.signal
    async def stop(self) -> None:
        self._stop_requested = True
        self._paused = False
        self._stats["status"] = "stopping"
        workflow.logger.info("Shutdown requested.")

    @workflow.query
    def get_stats(self) -> dict:
        return self._stats

    async def _wait_if_paused(self) -> None:
        while self._paused and not self._stop_requested:
            await workflow.sleep(timedelta(seconds=1))


# ---------------------------------------------------------------------------
# Workflow: AFK Gift Farm
# ---------------------------------------------------------------------------

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
        _resume_stats: Optional[dict] = None,
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
                    "Cycle #%d | gifts=%d ammo=%d",
                    cycle, self._stats["gifts"], self._stats["ammo_crafted"]
                )

                if screenshot_every_cycles > 0 and cycle % screenshot_every_cycles == 0:
                    await _screenshot(f"gift_cycle_{cycle}")

                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=GAME_RETRY,
                )
                if collected:
                    self._stats["gifts"] += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=5),
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


# ---------------------------------------------------------------------------
# Workflow: Combat Patrol
# ---------------------------------------------------------------------------

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
        _resume_stats: Optional[dict] = None,
    ) -> dict:
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
                schedule_to_close_timeout=timedelta(seconds=5),
                retry_policy=GAME_RETRY,
            )

            if not enemy["found"]:
                await workflow.sleep(timedelta(seconds=1))
                continue

            if enemy["hazard"]:
                workflow.logger.warning(
                    "Hazard enemy '%s' at (%d,%d) — retreating without engaging.",
                    enemy["type"], enemy["x"], enemy["y"]
                )
                await workflow.execute_activity(
                    retreat_from_hazard,
                    schedule_to_close_timeout=timedelta(seconds=10),
                    retry_policy=NO_RETRY,
                )
                await workflow.sleep(timedelta(seconds=10))
                continue

            workflow.logger.info(
                "Enemy '%s' at (%d,%d)", enemy["type"], enemy["x"], enemy["y"]
            )

            result = await workflow.execute_activity(
                engage_enemy,
                args=[enemy["x"], enemy["y"]],
                schedule_to_close_timeout=timedelta(seconds=30),
                heartbeat_timeout=timedelta(seconds=5),
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
                    schedule_to_close_timeout=timedelta(seconds=15),
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


# ---------------------------------------------------------------------------
# Workflow: Full AFK Session
# ---------------------------------------------------------------------------

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
    ) -> dict:
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
        for rotation in range(total_rotations):
            if self._stop_requested:
                break
            await self._wait_if_paused()

            self._stats["rotation"] = rotation + 1
            workflow.logger.info(
                "=== Rotation %d/%d | gifts=%d kills=%d ===",
                rotation + 1, total_rotations,
                self._stats["total_gifts"], self._stats["total_kills"]
            )

            if screenshot_every_rotations > 0 and (rotation + 1) % screenshot_every_rotations == 0:
                await _screenshot(f"rotation_{rotation + 1}")

            # Phase 1: Gift farming
            for _ in range(gift_cycles):
                if self._stop_requested:
                    break
                await self._wait_if_paused()

                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=GAME_RETRY,
                )
                if collected:
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
                        enemy["type"], enemy["x"], enemy["y"]
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


# ---------------------------------------------------------------------------
# Workflow: Manual Resource Harvesting
# ---------------------------------------------------------------------------

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
        _resume_stats: Optional[dict] = None,
    ) -> dict:
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
                    workflow.continue_as_new(
                        args=[swings_per_cycle, cycles, screenshot_every_cycles, self._stats]
                    )

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


# ---------------------------------------------------------------------------
# Workflow: Lizard Doggo Taming
# ---------------------------------------------------------------------------

@workflow.defn
class TameDoggoWorkflow(_ControlMixin):
    """
    Tries to tame a wild Lizard Doggo by repeatedly offering Paleberries
    (multiple doggos compete for the same berry, so repeating helps).

    Actual success — the Doggo ate, jumped, and "squeaked" — is not
    verified automatically (the visual cue is too weak for reliable
    template matching). Best-effort: review each attempt's screenshots
    manually in debug_screenshots/.

    Parameters:
        max_attempts (int):              Feeding attempts [5]
        seconds_between_attempts (int):  Wait between attempts [15]

    get_stats query returns:
        {attempts, fed, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"attempts": 0, "fed": 0, "status": "running"}

    @workflow.run
    async def run(self, max_attempts: int = 5, seconds_between_attempts: int = 15) -> dict:
        workflow.logger.info("TameDoggoWorkflow started. max_attempts=%d", max_attempts)
        try:
            while self._stats["attempts"] < max_attempts and not self._stop_requested:
                await self._wait_if_paused()
                if self._stop_requested:
                    break

                self._stats["attempts"] += 1
                attempt = self._stats["attempts"]

                fed = await workflow.execute_activity(
                    feed_wild_doggo,
                    start_to_close_timeout=timedelta(seconds=10),
                    schedule_to_close_timeout=timedelta(seconds=30),
                    retry_policy=GAME_RETRY,
                )
                if fed:
                    self._stats["fed"] += 1
                    await _screenshot(f"tame_attempt_{attempt}")

                await workflow.sleep(timedelta(seconds=seconds_between_attempts))

            self._stats["status"] = "stopped"
            await _save_stats("TameDoggoWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("TameDoggoWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("TameDoggoWorkflow"))
            raise


@workflow.defn
class TemplateOrchestrationWorkflow:
    """
    Workflow to automate template capture and visual verification.

    Parameters:
        target (str): "hud" or "workshop"
        resolution (str): "2560x1440"
    """

    @workflow.run
    async def run(self, target: str = "hud", resolution: str = "2560x1440") -> dict:
        workflow.logger.info("TemplateOrchestrationWorkflow started for target: %s", target)

        if target == "hud":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["hud_base", "", ""],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        elif target == "workshop":
            screenshot = await workflow.execute_activity(
                capture_template_screen,
                args=["workshop_base", "e", "escape"],
                schedule_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
        else:
            raise ValueError(f"Unknown target: {target}")

        extracted = await workflow.execute_activity(
            extract_templates_from_screen,
            args=[screenshot, target, resolution],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        template_names = list(extracted.keys())
        verification = await workflow.execute_activity(
            verify_matching_templates,
            args=[template_names],
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        return {
            "screenshot": screenshot,
            "extracted_templates": extracted,
            "verification_results": verification,
        }


# ---------------------------------------------------------------------------
# Workflow: Combat Expedition (go, kill, resupply, return, store)
# ---------------------------------------------------------------------------

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
            "kills": 0, "deaths": 0, "escaped": 0,
            "resupply_trips": 0, "status": "running",
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
    ) -> dict:
        workflow.logger.info(
            "CombatExpeditionWorkflow started. location=%s max_kills=%d", location, max_kills
        )
        nav_start_to_close = timedelta(seconds=nav_timeout_seconds)
        nav_schedule_to_close = nav_start_to_close * NAV_RETRY.maximum_attempts + timedelta(seconds=20)

        async def _go(target: str) -> None:
            await workflow.execute_activity(
                navigate_to_location,
                args=[target],
                start_to_close_timeout=nav_start_to_close,
                schedule_to_close_timeout=nav_schedule_to_close,
                heartbeat_timeout=timedelta(seconds=8),
                retry_policy=NAV_RETRY,
            )

        async def _ammo() -> int:
            return await workflow.execute_activity(
                check_ammo_count,
                schedule_to_close_timeout=timedelta(seconds=10),
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
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if not enemy["found"]:
                    await workflow.sleep(timedelta(seconds=1))
                    continue

                if enemy["hazard"]:
                    workflow.logger.warning(
                        "Hazard enemy '%s' at (%d,%d) — retreating without engaging.",
                        enemy["type"], enemy["x"], enemy["y"]
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
                        schedule_to_close_timeout=timedelta(seconds=15),
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
                start_to_close_timeout=timedelta(seconds=20),
                schedule_to_close_timeout=timedelta(seconds=70),
                retry_policy=GAME_RETRY,
            )

            self._stats["status"] = "completed"
            await _save_stats("CombatExpeditionWorkflow", self._stats)
            return self._stats
        except asyncio.CancelledError:
            workflow.logger.warning("CombatExpeditionWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("CombatExpeditionWorkflow"))
            raise


# ---------------------------------------------------------------------------
# Workflow: Exploration (blind traversal + screenshot collection)
# ---------------------------------------------------------------------------

@workflow.defn
class ExplorationWorkflow(_ControlMixin):
    """
    Unsupervised exploration around the base: captures a reference
    screenshot, then walks a configured route (config.toml
    [[exploration.route]]) leg by leg, optionally holding jump for
    Hover Pack ascend/glide, screenshotting and checking health/death
    after every leg. Stops early on low health, death, a 'stop' signal,
    or once max_total_duration_seconds of movement has been spent, then
    automatically retraces the legs taken (mirrored keys/turns) to head
    back toward the start.

    Blind and best-effort, like the rest of this bot's navigation — there
    is no real-time hazard awareness (cliffs, water, enemies), so keep
    config.toml [exploration] legs short and conservative.

    Parameters:
        max_total_duration_seconds (float, optional): overrides config.toml
        ignore_health_check (bool): skip the low-health abort [False] —
            'health_low_indicator' is currently miscalibrated (matches the
            always-present heart-rate HUD icon regardless of real health,
            see README "Known limitations"), so it aborts on leg 0 of every
            run. Only set this True if you are actively watching the
            screenshots as the run progresses; death detection still
            applies regardless of this flag.

    get_stats query returns:
        {legs_completed, health_aborts, died, returned, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {
            "legs_completed": 0, "health_aborts": 0, "died": 0,
            "returned": False, "status": "running",
        }

    @workflow.run
    async def run(
        self,
        max_total_duration_seconds: Optional[float] = None,
        ignore_health_check: bool = False,
    ) -> dict:
        workflow.logger.info("ExplorationWorkflow started.")
        try:
            return await self._run_exploration(max_total_duration_seconds, ignore_health_check)
        except asyncio.CancelledError:
            workflow.logger.warning("ExplorationWorkflow cancelled — cleaning up game state.")
            await asyncio.shield(_cleanup_on_cancel("ExplorationWorkflow"))
            raise

    async def _run_exploration(
        self, max_total_duration_seconds: Optional[float], ignore_health_check: bool = False,
    ) -> dict:
        route_cfg = await workflow.execute_activity(
            get_exploration_route,
            schedule_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        route = route_cfg["route"]
        max_duration = (
            max_total_duration_seconds
            if max_total_duration_seconds is not None
            else route_cfg["max_total_duration_seconds"]
        )
        check_interval = route_cfg["check_interval"]
        ascend_every = route_cfg["ascend_every"]
        ascend_pulse = route_cfg["ascend_pulse"]

        await workflow.execute_activity(
            capture_base_reference,
            start_to_close_timeout=timedelta(seconds=25),
            schedule_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        legs_taken: list[dict] = []
        elapsed = 0.0
        died_mid_route = False

        # Vision captures on this system occasionally fall back to a slow
        # ImageMagick subprocess, so timeouts are generous. More importantly:
        # any failure here (timeout, vision error, etc.) must still fall
        # through to the mirrored return below instead of leaving the
        # character stranded mid-route — that's why activity errors are
        # caught here rather than left to propagate.
        for i, leg in enumerate(route):
            if self._stop_requested:
                break
            await self._wait_if_paused()
            if self._stop_requested:
                break

            duration = leg.get("duration", 1.0)
            if elapsed + duration > max_duration:
                workflow.logger.info(
                    "Reached max_total_duration_seconds (%.1fs) — stopping the outbound route.",
                    max_duration,
                )
                break

            # Budget per chunk, not just per leg: a single chunk's capture+
            # checks took ~9s live on this system (mss falling back to a
            # slow ImageMagick subprocess), so a leg with several chunks
            # needs a timeout that scales with chunk count, not just
            # nominal movement duration.
            num_chunks = max(1, math.ceil(duration / check_interval)) if check_interval > 0 else 1
            chunk_budget = num_chunks * 15 + 20
            try:
                result = await workflow.execute_activity(
                    explore_leg,
                    args=[
                        leg.get("keys", ["w"]), duration, leg.get("turn_dx", 0), i,
                        check_interval, ascend_every, ascend_pulse,
                    ],
                    start_to_close_timeout=timedelta(seconds=chunk_budget),
                    schedule_to_close_timeout=timedelta(seconds=chunk_budget + 20),
                    heartbeat_timeout=timedelta(seconds=20),
                    retry_policy=NO_RETRY,
                )
            except Exception as exc:
                workflow.logger.error(
                    "Leg %d failed (%s) — stopping the outbound route and retracing what was already taken.",
                    i, exc,
                )
                break

            legs_taken.append(result)
            elapsed += duration
            self._stats["legs_completed"] += 1

            if result["died"]:
                died_mid_route = True
                self._stats["died"] += 1
                workflow.logger.warning("Death detected mid-exploration — respawning instead of retracing.")
                break

            if result["health_low"] and not ignore_health_check:
                self._stats["health_aborts"] += 1
                workflow.logger.warning("Low health mid-exploration — aborting outbound route early.")
                break

        if died_mid_route:
            await workflow.execute_activity(
                handle_death_respawn,
                schedule_to_close_timeout=timedelta(seconds=15),
                retry_policy=NAV_RETRY,
            )
            self._stats["status"] = "died"
            await _save_stats("ExplorationWorkflow", self._stats)
            return self._stats

        if legs_taken:
            return_budget = sum(l["duration"] for l in legs_taken)
            try:
                await workflow.execute_activity(
                    return_via_reverse_route,
                    args=[legs_taken],
                    start_to_close_timeout=timedelta(seconds=return_budget + 40),
                    schedule_to_close_timeout=timedelta(seconds=return_budget + 70),
                    heartbeat_timeout=timedelta(seconds=15),
                    retry_policy=NO_RETRY,
                )
                self._stats["returned"] = True
            except Exception as exc:
                workflow.logger.error("Return trip failed (%s) — character may not be back at the start.", exc)

        self._stats["status"] = "completed"
        await _save_stats("ExplorationWorkflow", self._stats)
        return self._stats
