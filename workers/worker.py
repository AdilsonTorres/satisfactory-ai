"""
workers/worker.py

Worker do Temporal — registra workflows e activities e conecta ao servidor.

Pré-requisito: servidor Temporal rodando (docker compose up -d)

Como rodar:
    uv run python workers/worker.py

Disparo de workflows:
    temporal workflow start --workflow-type GiftFarmWorkflow --task-queue satisfactory-bot --input '{}'
    temporal workflow start --workflow-type CombatPatrolWorkflow --task-queue satisfactory-bot --input '{"max_kills": 20}'
    temporal workflow start --workflow-type AfkSessionWorkflow --task-queue satisfactory-bot --input '{}'

Controle em runtime:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
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
    take_debug_screenshot,
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
TEMPORAL_ADDRESS = "localhost:7233"


async def main() -> None:
    logger.info("Conectando ao Temporal em %s ...", TEMPORAL_ADDRESS)
    client = await Client.connect(TEMPORAL_ADDRESS)
    logger.info("Conectado.")

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
            take_debug_screenshot,
        ],
        # Inputs são sequenciais — manter em 1 para não sobrepor ações no jogo
        max_concurrent_activities=1,
    ):
        logger.info("Worker ativo. Task queue: '%s'", TASK_QUEUE)
        logger.info("UI Temporal: http://localhost:8233")
        logger.info("Aguardando workflows... (Ctrl+C para parar)")
        await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
