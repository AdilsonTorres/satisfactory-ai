"""
workers/worker.py

Ponto de entrada do worker Temporal.
Logging e configuração são lidos de config.toml.

Pré-requisito: docker compose up -d

Como rodar:
    uv run python workers/worker.py

Controle de workflows em runtime:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""
import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from utils import config as cfg
from utils import logger as log

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
from workflows.satisfactory_workflows import (
    GiftFarmWorkflow,
    CombatPatrolWorkflow,
    AfkSessionWorkflow,
)

_logger = logging.getLogger(__name__)


async def main() -> None:
    log.setup(cfg.get("logging.level", "INFO"))

    address = cfg.get("temporal.address", "localhost:7233")
    task_queue = cfg.get("temporal.task_queue", "satisfactory-bot")

    _logger.info("Conectando ao Temporal em %s ...", address)
    client = await Client.connect(address)
    _logger.info("Conectado. Task queue: '%s'", task_queue)

    async with Worker(
        client,
        task_queue=task_queue,
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
            persist_session_stats,
        ],
        # Inputs são sequenciais — manter em 1 para não sobrepor ações no jogo
        max_concurrent_activities=1,
    ):
        _logger.info("Worker ativo. UI: http://localhost:8233 | Ctrl+C para parar")
        await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
