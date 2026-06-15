"""
workflows/satisfactory_workflows.py

Workflows com:
- Signals: pause / resume / stop
- Queries: get_stats
- Screenshots periódicos configuráveis
- Estatísticas persistidas em JSON ao final (via persist_session_stats activity)

Controle via CLI:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""
import logging
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities.game_activities import (
        collect_doggo_gift,
        check_inventory_full,
        check_health_low,
        navigate_to_equipment_workshop,
        craft_rifle_ammo,
        navigate_back_to_base,
        scan_for_enemy,
        engage_enemy,
        handle_death_respawn,
        take_debug_screenshot,
        persist_session_stats,
    )

logger = logging.getLogger(__name__)

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
    # FileNotFoundError = template faltando = bug, não retry
    # NavigationError after max_attempts = aborta o workflow
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


async def _run_craft_cycle(ammo_per_craft: int) -> None:
    await workflow.execute_activity(
        navigate_to_equipment_workshop,
        schedule_to_close_timeout=timedelta(seconds=20),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=NAV_RETRY,
    )
    await workflow.execute_activity(
        craft_rifle_ammo,
        args=[ammo_per_craft],
        schedule_to_close_timeout=timedelta(seconds=30),
        heartbeat_timeout=timedelta(seconds=8),
        retry_policy=GAME_RETRY,
    )
    await workflow.execute_activity(
        navigate_back_to_base,
        schedule_to_close_timeout=timedelta(seconds=20),
        retry_policy=NAV_RETRY,
    )


# ---------------------------------------------------------------------------
# Mixin de controle (pause / resume / stop / get_stats)
# ---------------------------------------------------------------------------

class _ControlMixin:
    """Signals e query compartilhados por todos os workflows."""

    def __init__(self) -> None:
        self._paused = False
        self._stop_requested = False
        self._stats: dict = {"status": "running"}

    @workflow.signal
    async def pause(self) -> None:
        self._paused = True
        self._stats["status"] = "paused"
        workflow.logger.info("Pausado.")

    @workflow.signal
    async def resume(self) -> None:
        self._paused = False
        self._stats["status"] = "running"
        workflow.logger.info("Retomado.")

    @workflow.signal
    async def stop(self) -> None:
        self._stop_requested = True
        self._paused = False
        self._stats["status"] = "stopping"
        workflow.logger.info("Encerramento solicitado.")

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
    Loop de AFK farm de gifts dos Lizard Doggos.

    Parâmetros:
        ammo_per_craft (int):           Rifle Ammo por ciclo de craft [50]
        screenshot_every_cycles (int):  Screenshot a cada N ciclos [10]

    Query get_stats retorna:
        {gifts, ammo_crafted, cycles, status}
    """

    def __init__(self) -> None:
        super().__init__()
        self._stats = {"gifts": 0, "ammo_crafted": 0, "cycles": 0, "status": "running"}

    @workflow.run
    async def run(self, ammo_per_craft: int = 50, screenshot_every_cycles: int = 10) -> dict:
        workflow.logger.info("GiftFarmWorkflow iniciado.")

        while not self._stop_requested:
            await self._wait_if_paused()
            if self._stop_requested:
                break

            self._stats["cycles"] += 1
            cycle = self._stats["cycles"]
            workflow.logger.info(
                "Ciclo #%d | gifts=%d ammo=%d",
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


# ---------------------------------------------------------------------------
# Workflow: Patrulha de Combate
# ---------------------------------------------------------------------------

@workflow.defn
class CombatPatrolWorkflow(_ControlMixin):
    """
    Patrulha estática: fica no lugar e reage a inimigos que entram no campo de visão.

    Parâmetros:
        max_kills (int):               Kills para encerrar [20]
        screenshot_every_kills (int):  Screenshot a cada N kills [5]

    Query get_stats retorna:
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
    ) -> dict:
        workflow.logger.info("CombatPatrolWorkflow iniciado. max_kills=%d", max_kills)

        while self._stats["kills"] < max_kills and not self._stop_requested:
            await self._wait_if_paused()
            if self._stop_requested:
                break

            enemy = await workflow.execute_activity(
                scan_for_enemy,
                schedule_to_close_timeout=timedelta(seconds=5),
                retry_policy=GAME_RETRY,
            )

            if not enemy["found"]:
                await workflow.sleep(timedelta(seconds=1))
                continue

            workflow.logger.info(
                "Inimigo '%s' em (%d,%d)", enemy["type"], enemy["x"], enemy["y"]
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
                workflow.logger.warning("Morreu (morte #%d). Respawnando...", self._stats["deaths"])
                await workflow.execute_activity(
                    handle_death_respawn,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=NAV_RETRY,
                )
                await workflow.sleep(timedelta(seconds=5))

            elif result == "escaped":
                self._stats["escaped"] += 1
                workflow.logger.info("Fugiu (vida baixa). Aguardando regeneração.")
                await workflow.sleep(timedelta(seconds=8))

        self._stats["status"] = "stopped"
        await _save_stats("CombatPatrolWorkflow", self._stats)
        return self._stats


# ---------------------------------------------------------------------------
# Workflow: Sessão AFK Completa
# ---------------------------------------------------------------------------

@workflow.defn
class AfkSessionWorkflow(_ControlMixin):
    """
    Rotações alternadas de gift farm + patrulha de combate.

    Parâmetros:
        gift_cycles (int):                  Ciclos de gift por rotação [10]
        combat_kills_per_rotation (int):    Kills de combate por rotação [5]
        total_rotations (int):              Total de rotações [20]
        screenshot_every_rotations (int):   Screenshot a cada N rotações [1]

    Query get_stats retorna:
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

        for rotation in range(total_rotations):
            if self._stop_requested:
                break
            await self._wait_if_paused()

            self._stats["rotation"] = rotation + 1
            workflow.logger.info(
                "=== Rotação %d/%d | gifts=%d kills=%d ===",
                rotation + 1, total_rotations,
                self._stats["total_gifts"], self._stats["total_kills"]
            )

            if screenshot_every_rotations > 0 and (rotation + 1) % screenshot_every_rotations == 0:
                await _screenshot(f"rotation_{rotation + 1}")

            # Fase 1: Gift farm
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

            # Fase 2: Combate
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
