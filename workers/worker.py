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

from activities import ALL_ACTIVITIES
from utils import config as cfg
from utils import logger as log
from workflows import ALL_WORKFLOWS

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
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
        # Inputs are sequential — keep at 1 so actions in the game don't overlap
        max_concurrent_activities=1,
    ):
        _logger.info("Worker active. UI: http://localhost:8233 | Ctrl+C to stop")
        await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
