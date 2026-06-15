"""
workers/worker.py

Worker do Temporal — registra workflows e activities, conecta ao servidor.

Como rodar (após `docker compose up -d`):

    uv run python workers/worker.py

Disparo de workflow:

    temporal workflow start \\
        --workflow-type GiftFarmWorkflow \\
        --task-queue satisfactory-bot \\
        --input '{}'
"""
import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

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
from workflows.satisfactory_workflows import (
    GiftFarmWorkflow,
    CombatPatrolWorkflow,
    AfkSessionWorkflow,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TASK_QUEUE = "satisfactory-bot"


async def main():
    logger.info("Conectando ao Temporal em localhost:7233 ...")
    client = await Client.connect("localhost:7233")

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            GiftFarmWorkflow,
            CombatPatrolWorkflow,
            AfkSessionWorkflow,
        ],
        activities=[
            collect_doggo_gift,
            check_inventory_full,
            check_health_low,
            navigate_to_equipment_workshop,
            craft_rifle_ammo,
            navigate_back_to_base,
            scan_for_enemy,
            engage_enemy,
            handle_death_respawn,
        ],
        # Inputs são sequenciais — manter em 1 para não sobrepor ações no jogo
        max_concurrent_activities=1,
    ):
        logger.info("Worker rodando. Task queue: '%s'. Aguardando workflows...", TASK_QUEUE)
        logger.info("Para parar: Ctrl+C")
        await asyncio.Future()


def run():
    asyncio.run(main())


if __name__ == "__main__":
    run()
