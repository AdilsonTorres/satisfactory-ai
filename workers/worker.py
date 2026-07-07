"""
workers/worker.py

HOST game worker — activity-only.

Runs the game-driving activities (screen capture, uinput, KWin focus) and
therefore MUST run directly on the desktop session, not in Docker. It
registers NO workflows: workflow tasks on the same queue are polled only by
the Dockerized orchestrator worker (workers/orchestrator.py) — Temporal
routes workflow tasks and activity tasks independently, so both workers
share one task queue without stepping on each other.

Prerequisite: docker compose up -d   (temporal + orchestrator worker)

How to run:
    uv run python workers/worker.py
(or install the systemd user service — see docs/deploy.md)

Runtime workflow control:
    temporal workflow signal --workflow-id <id> --name pause
    temporal workflow signal --workflow-id <id> --name resume
    temporal workflow signal --workflow-id <id> --name stop
    temporal workflow query  --workflow-id <id> --query-type get_stats
"""

import asyncio
import logging
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from activities import GAME_ACTIVITIES
from utils import config as cfg
from utils import logger as log

_logger = logging.getLogger(__name__)


async def main() -> None:
    log.setup(cfg.get("logging.level", "INFO"))

    address = cfg.get("temporal.address", "localhost:7233")
    task_queue = cfg.get("temporal.task_queue", "satisfactory-bot")

    _logger.info("Connecting to Temporal at %s ...", address)
    client = await Client.connect(address)
    _logger.info("Connected. Game-activity queue: '%s'", task_queue)

    # Activities are sync (they drive the game with blocking sleeps/IO), so
    # they run on this executor instead of blocking the asyncio event loop —
    # a blocked loop would stall heartbeats and workflow task processing.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="activity") as activity_executor:
        async with Worker(
            client,
            task_queue=task_queue,
            activities=GAME_ACTIVITIES,
            activity_executor=activity_executor,
            # Inputs are sequential — keep at 1 so actions in the game don't overlap
            max_concurrent_activities=1,
            identity=f"satisfactory-game-worker@{socket.gethostname()}",
            # On shutdown, give in-flight activities a cancellation notice and
            # this long to finish (e.g. close menus) before being dropped.
            graceful_shutdown_timeout=timedelta(seconds=10),
        ):
            _logger.info("Game worker active. UI: http://localhost:8233 | Ctrl+C to stop")
            await asyncio.Future()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
