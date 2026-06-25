"""
workers/worker.py

Temporal worker entry point.
Logging and configuration are read from config.toml.

Prerequisite: docker compose up -d

How to run:
    uv run python workers/worker.py

Runtime workflow control:
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
from workflows.satisfactory_workflows import (
    GiftFarmWorkflow,
    CombatPatrolWorkflow,
    AfkSessionWorkflow,
    TemplateOrchestrationWorkflow,
    ResourceHarvestWorkflow,
    TameDoggoWorkflow,
    CombatExpeditionWorkflow,
    ExplorationWorkflow,
)

_logger = logging.getLogger(__name__)


async def main() -> None:
    log.setup(cfg.get("logging.level", "INFO"))

    address = cfg.get("temporal.address", "localhost:7233")
    task_queue = cfg.get("temporal.task_queue", "satisfactory-bot")

    _logger.info("Connecting to Temporal at %s ...", address)
    client = await Client.connect(address)
    _logger.info("Connected. Task queue: '%s'", task_queue)

    async with Worker(
        client,
        task_queue=task_queue,
        workflows=[
            GiftFarmWorkflow,
            CombatPatrolWorkflow,
            AfkSessionWorkflow,
            TemplateOrchestrationWorkflow,
            ResourceHarvestWorkflow,
            TameDoggoWorkflow,
            CombatExpeditionWorkflow,
            ExplorationWorkflow,
        ],
        activities=[
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
        ],
        # Inputs are sequential — keep at 1 so actions in the game don't overlap
        max_concurrent_activities=1,
    ):
        _logger.info("Worker active. UI: http://localhost:8233 | Ctrl+C to stop")
        await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
