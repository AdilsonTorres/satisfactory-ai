"""
workflows/satisfactory_workflows.py

Workflows do Temporal — orquestram as activities em lógica de alto nível.

Por que Temporal aqui?
- Retry automático: se o menu não abriu, tenta de novo sem você fazer nada
- Histórico: quando o bot morreu às 14h32, você vê EXATAMENTE o que estava fazendo
- Pausável: você pode pausar o workflow pelo terminal e retomar depois
- Timeouts: se uma activity travar, o Temporal mata e faz retry
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
    )

logger = logging.getLogger(__name__)

GAME_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_attempts=3,
    backoff_coefficient=2.0,
    non_retryable_error_types=["FileNotFoundError"],
)

NAV_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    maximum_attempts=5,
    backoff_coefficient=1.5,
)


# ---------------------------------------------------------------------------
# Workflow: AFK Gift Farm
# ---------------------------------------------------------------------------

@workflow.defn
class GiftFarmWorkflow:
    """
    Loop principal de AFK farm de gifts dos Lizard Doggos.

    Ciclo: espera gift → coleta → checa inventário → crafta se cheio → repete

    Uso:
        temporal workflow start \\
            --workflow-type GiftFarmWorkflow \\
            --task-queue satisfactory-bot \\
            --input '{"craft_threshold": 40, "ammo_per_craft": 50}'
    """

    @workflow.run
    async def run(self, craft_threshold: int = 40, ammo_per_craft: int = 50) -> str:
        gifts_collected = 0
        ammo_crafted = 0
        cycles = 0

        workflow.logger.info(
            "GiftFarmWorkflow iniciado. craft_threshold=%d, ammo_per_craft=%d",
            craft_threshold, ammo_per_craft
        )

        while True:
            cycles += 1
            workflow.logger.info("--- Ciclo #%d | Gifts: %d | Ammo craftada: %d ---",
                                  cycles, gifts_collected, ammo_crafted)

            collected = await workflow.execute_activity(
                collect_doggo_gift,
                schedule_to_close_timeout=timedelta(seconds=15),
                retry_policy=GAME_RETRY,
            )
            if collected:
                gifts_collected += 1

            inv_full = await workflow.execute_activity(
                check_inventory_full,
                schedule_to_close_timeout=timedelta(seconds=5),
                retry_policy=GAME_RETRY,
            )

            if inv_full:
                workflow.logger.info("Inventário cheio — indo craftar munição.")
                await _run_craft_cycle(ammo_per_craft)
                ammo_crafted += ammo_per_craft

            await workflow.sleep(timedelta(seconds=3))


# ---------------------------------------------------------------------------
# Workflow: Patrulha de Combate
# ---------------------------------------------------------------------------

@workflow.defn
class CombatPatrolWorkflow:
    """
    Patrulha uma área pré-definida, mata inimigos e coleta remains.

    Estratégia: defesa estática com scan em intervalos.
    Não faz pathfinding — o personagem fica na mesma posição base
    e reage a inimigos que entram no campo de visão.

    Uso:
        temporal workflow start \\
            --workflow-type CombatPatrolWorkflow \\
            --task-queue satisfactory-bot \\
            --input '{"max_kills": 20, "screen_w": 1920, "screen_h": 1080}'
    """

    @workflow.run
    async def run(self, max_kills: int = 20, screen_w: int = 1920, screen_h: int = 1080) -> dict:
        kills = 0
        deaths = 0
        escaped = 0

        workflow.logger.info("CombatPatrolWorkflow iniciado. max_kills=%d", max_kills)

        while kills < max_kills:
            enemy = await workflow.execute_activity(
                scan_for_enemy,
                schedule_to_close_timeout=timedelta(seconds=5),
                retry_policy=GAME_RETRY,
            )

            if not enemy["found"]:
                await workflow.sleep(timedelta(seconds=1))
                continue

            workflow.logger.info(
                "Inimigo detectado! Engajando em (%d, %d)", enemy["x"], enemy["y"]
            )

            result = await workflow.execute_activity(
                engage_enemy,
                args=[enemy["x"], enemy["y"], screen_w, screen_h],
                schedule_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )

            if result == "killed":
                kills += 1
                workflow.logger.info("Kill #%d confirmado.", kills)

            elif result == "died":
                deaths += 1
                workflow.logger.warning("Morreu! Tentando respawn... (morte #%d)", deaths)

                respawned = await workflow.execute_activity(
                    handle_death_respawn,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=NAV_RETRY,
                )
                if not respawned:
                    workflow.logger.error("Falha no respawn — abortando workflow.")
                    break

                await workflow.sleep(timedelta(seconds=5))

            elif result == "escaped":
                escaped += 1
                workflow.logger.info("Fugiu do combate (vida baixa). Aguardando regeneração.")
                await workflow.sleep(timedelta(seconds=8))

        summary = {"kills": kills, "deaths": deaths, "escaped": escaped}
        workflow.logger.info("CombatPatrolWorkflow finalizado: %s", summary)
        return summary


# ---------------------------------------------------------------------------
# Workflow: Sessão Completa AFK (combina tudo)
# ---------------------------------------------------------------------------

@workflow.defn
class AfkSessionWorkflow:
    """
    Workflow principal que combina farm de gifts + patrulha de combate.

    Uso:
        temporal workflow start \\
            --workflow-type AfkSessionWorkflow \\
            --task-queue satisfactory-bot \\
            --input '{
                "gift_cycles": 10,
                "combat_kills_per_rotation": 5,
                "total_rotations": 20
            }'
    """

    @workflow.run
    async def run(
        self,
        gift_cycles: int = 10,
        combat_kills_per_rotation: int = 5,
        total_rotations: int = 20,
    ) -> dict:

        total_gifts = 0
        total_kills = 0
        total_ammo = 0

        for rotation in range(total_rotations):
            workflow.logger.info("=== Rotação %d/%d ===", rotation + 1, total_rotations)

            for _ in range(gift_cycles):
                collected = await workflow.execute_activity(
                    collect_doggo_gift,
                    schedule_to_close_timeout=timedelta(seconds=15),
                    retry_policy=GAME_RETRY,
                )
                if collected:
                    total_gifts += 1

                inv_full = await workflow.execute_activity(
                    check_inventory_full,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if inv_full:
                    await _run_craft_cycle(ammo_per_craft=50)
                    total_ammo += 50

                await workflow.sleep(timedelta(seconds=3))

            for _ in range(combat_kills_per_rotation):
                enemy = await workflow.execute_activity(
                    scan_for_enemy,
                    schedule_to_close_timeout=timedelta(seconds=5),
                    retry_policy=GAME_RETRY,
                )
                if enemy["found"]:
                    result = await workflow.execute_activity(
                        engage_enemy,
                        args=[enemy["x"], enemy["y"]],
                        schedule_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                    )
                    if result == "killed":
                        total_kills += 1
                    elif result == "died":
                        await workflow.execute_activity(
                            handle_death_respawn,
                            schedule_to_close_timeout=timedelta(seconds=15),
                            retry_policy=NAV_RETRY,
                        )
                        await workflow.sleep(timedelta(seconds=5))

                await workflow.sleep(timedelta(seconds=2))

        return {
            "total_gifts": total_gifts,
            "total_kills": total_kills,
            "total_ammo_crafted": total_ammo,
        }


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

async def _run_craft_cycle(ammo_per_craft: int):
    """Navega até o workshop, crafa e volta."""
    await workflow.execute_activity(
        navigate_to_equipment_workshop,
        schedule_to_close_timeout=timedelta(seconds=20),
        retry_policy=NAV_RETRY,
    )
    await workflow.execute_activity(
        craft_rifle_ammo,
        args=[ammo_per_craft],
        schedule_to_close_timeout=timedelta(seconds=30),
        retry_policy=GAME_RETRY,
    )
    await workflow.execute_activity(
        navigate_back_to_base,
        schedule_to_close_timeout=timedelta(seconds=20),
        retry_policy=NAV_RETRY,
    )
